"""Track macOS shared camera streams from narrowly filtered CoreMediaIO events.

AVFoundation's other-app flag stays false when cameras are shared. CMIO's stream events
identify the client PID even in that case. A live log stream runs in the background; a
history snapshot also catches calls already active when Hands Down starts. No frames or
log files are recorded. Only stream state, timestamps, PIDs and executable paths are kept.
"""

import ctypes
import json
import os
import re
import subprocess
import threading
from datetime import datetime

PREDICATE = ('subsystem == "com.apple.cmio" AND '
             'eventMessage CONTAINS "CMIO_DAL_CMIOExtension_Device.mm" AND '
             '(eventMessage CONTAINS ":StartStream " OR eventMessage CONTAINS ":StopStream ")')
STREAM_EVENT = re.compile(r'CMIO_DAL_CMIOExtension_Device\.mm:\d+:(StartStream|StopStream) (\d+), (\d+)\s*$')


class MacStreamActivity:
    def __init__(self, own_pid=None):
        self._own_pid = os.getpid() if own_pid is None else own_pid
        self._streams = {}
        self._lock = threading.Lock()

    def consume(self, event) -> None:
        if not isinstance(event, dict):
            return
        match = STREAM_EVENT.search(event.get('eventMessage', ''))
        if match is None:
            return
        try:
            pid = int(event['processID'])
            stamp = datetime.fromisoformat(event['timestamp']).timestamp()
            path = event['processImagePath']
        except (KeyError, TypeError, ValueError):
            return
        if pid <= 0 or not isinstance(path, str) or not path.startswith('/'):
            return
        action, device, stream = match.groups()
        key = (pid, device, stream)
        with self._lock:
            previous = self._streams.get(key)
            if previous is None or stamp > previous[0]:
                self._streams[key] = (stamp, action == 'StartStream', path)

    def active_clients(self, alive) -> list[tuple[int, str]]:
        with self._lock:
            clients = {(key[0], value[2]) for key, value in self._streams.items()
                       if value[1] and key[0] != self._own_pid}
        return [(pid, path) for pid, path in clients if alive(pid, path)]

    def other_camera_users(self, alive) -> bool:
        return bool(self.active_clients(alive))


def process_matches(pid, expected_path) -> bool:
    lib = ctypes.CDLL('/usr/lib/libproc.dylib')
    lib.proc_pidpath.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32]
    lib.proc_pidpath.restype = ctypes.c_int
    buffer = ctypes.create_string_buffer(4096)
    return lib.proc_pidpath(pid, buffer, len(buffer)) > 0 and os.fsdecode(buffer.value) == expected_path


def cameras_running() -> bool | None:
    """CoreMediaIO's 'running somewhere' flag; use only when we own no camera feed."""
    class Address(ctypes.Structure):
        _fields_ = [('selector', ctypes.c_uint32), ('scope', ctypes.c_uint32), ('element', ctypes.c_uint32)]
    lib = ctypes.CDLL('/System/Library/Frameworks/CoreMediaIO.framework/CoreMediaIO')
    lib.CMIOObjectGetPropertyDataSize.argtypes = [ctypes.c_uint32, ctypes.POINTER(Address), ctypes.c_uint32,
                                                ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
    lib.CMIOObjectGetPropertyDataSize.restype = ctypes.c_int32
    lib.CMIOObjectGetPropertyData.argtypes = [ctypes.c_uint32, ctypes.POINTER(Address), ctypes.c_uint32,
                                            ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32), ctypes.c_void_p]
    lib.CMIOObjectGetPropertyData.restype = ctypes.c_int32
    address = Address(int.from_bytes(b'dev#', 'big'), int.from_bytes(b'glob', 'big'), 0)
    size = ctypes.c_uint32()
    if lib.CMIOObjectGetPropertyDataSize(1, ctypes.byref(address), 0, None, ctypes.byref(size)):
        return None
    devices = (ctypes.c_uint32 * (size.value // 4))()
    if lib.CMIOObjectGetPropertyData(1, ctypes.byref(address), 0, None, size.value, ctypes.byref(size), devices):
        return None
    address.selector = int.from_bytes(b'gone', 'big')
    known = False
    for device in devices:
        running = ctypes.c_uint32()
        data_size = ctypes.c_uint32(4)
        if lib.CMIOObjectGetPropertyData(device, ctypes.byref(address), 0, None,
                                        4, ctypes.byref(data_size), ctypes.byref(running)) == 0:
            known = True
            if running.value:
                return True
    return False if known else None


class MacCameraActivity:
    def __init__(self, popen=subprocess.Popen, alive=process_matches, running=cameras_running):
        self.activity = MacStreamActivity()
        self._popen = popen
        self._alive = alive
        self._running = running
        self._capture_active = False
        self._ready = threading.Event()
        self._closed = threading.Event()
        self._lock = threading.Lock()
        self._started = False
        self._processes = []
        self._error = None
        self._history_error = None

    def _spawn(self, args):
        with self._lock:
            if self._closed.is_set():
                raise OSError('Camera activity monitor closed')
            process = self._popen(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
            self._processes.append(process)
        return process

    def _consume_line(self, line):
        try:
            self.activity.consume(json.loads(line))
        except (ValueError, TypeError):
            pass  # log stream headers and unrelated/malformed records are not camera events

    def _listen(self):
        try:
            process = self._spawn(['/usr/bin/log', 'stream', '--style', 'ndjson', '--level', 'debug',
                                   '--predicate', PREDICATE])
            # Start listening first; timestamp ordering protects against older bootstrap events.
            threading.Thread(target=self._bootstrap, name='camera-activity-history', daemon=True).start()
            for line in process.stdout:
                if self._closed.is_set():
                    break
                self._consume_line(line)
            if not self._closed.is_set():
                raise OSError('macOS camera activity stream ended')
        except Exception as exc:
            if not self._closed.is_set():
                self._error = str(exc)
                self._ready.set()

    def _bootstrap(self):
        process = None
        try:
            process = self._spawn(['/usr/bin/log', 'show', '--last', '1d', '--info', '--debug',
                                   '--style', 'ndjson', '--predicate', PREDICATE])
            output, _ = process.communicate(timeout=20)
            if process.returncode:
                raise OSError('macOS camera activity history unavailable')
            for line in output.splitlines():
                self._consume_line(line)
        except Exception as exc:
            if not self._closed.is_set():
                self._history_error = str(exc)
            if process is not None and process.poll() is None:
                process.kill()
                process.wait()
        finally:
            self._ready.set()

    def __call__(self, _index) -> bool | None:
        with self._lock:
            if not self._started and not self._closed.is_set():
                self._started = True
                threading.Thread(target=self._listen, name='camera-activity-events', daemon=True).start()
        if not self._capture_active and not self._closed.is_set():
            running = self._running()
            if running is not None:
                return running
        if self._error:
            raise OSError(self._error)
        if self._closed.is_set():
            return None
        # Positive live evidence is enough even if history is slow or unavailable.
        if self.activity.other_camera_users(self._alive):
            return True
        if not self._ready.is_set() or self._history_error:
            return None
        # CMIO client stream IDs are local to each process, so yield for any other camera user.
        return False

    def set_capture_active(self, active):
        self._capture_active = active

    def close(self):
        self._closed.set()
        with self._lock:
            processes = list(self._processes)
        for process in processes:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=2)
            if process.stdout is not None:
                process.stdout.close()
