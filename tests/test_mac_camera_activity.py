from handsdown import mac_camera_activity as camera_usage


def event(pid, action, time='2026-10-14 11:33:50.805630+0100', stream=39, path=None):
    return {'timestamp': time, 'subsystem': 'com.apple.cmio', 'processID': pid,
            'processImagePath': path or f'/apps/{pid}',
            'eventMessage': f'CMIO_DAL_CMIOExtension_Device.mm:1599:{action} 38, {stream}'}


def test_shared_camera_stream_pauses_even_when_avfoundation_flag_is_false():
    state = camera_usage.MacStreamActivity(own_pid=100)
    state.consume(event(100, 'StartStream'))
    assert not state.other_camera_users(lambda pid, path: True)
    state.consume(event(200, 'StartStream'))  # Teams starts a shared stream
    assert state.other_camera_users(lambda pid, path: True)
    state.consume(event(200, 'StopStream', '2026-10-14 11:34:00+0100'))
    assert not state.other_camera_users(lambda pid, path: True)


def test_bootstrap_events_cannot_overwrite_a_newer_live_stop():
    state = camera_usage.MacStreamActivity(own_pid=100)
    state.consume(event(200, 'StopStream', '2026-10-14 11:35:00+0100'))
    state.consume(event(200, 'StartStream'))
    assert not state.other_camera_users(lambda pid, path: True)


def test_stale_processes_and_reused_pids_are_not_treated_as_camera_users():
    state = camera_usage.MacStreamActivity(own_pid=100)
    state.consume(event(200, 'StartStream', path='/Applications/Teams.app/Teams'))
    assert not state.other_camera_users(lambda pid, path: path == '/different/process')


def test_multiple_streams_require_each_stream_to_stop():
    state = camera_usage.MacStreamActivity(own_pid=100)
    state.consume(event(200, 'StartStream', stream=39))
    state.consume(event(200, 'StartStream', stream=40))
    state.consume(event(200, 'StopStream', stream=39, time='2026-10-14 11:34:00+0100'))
    assert state.other_camera_users(lambda pid, path: True)


def test_non_stream_logs_and_malformed_events_do_not_activate_camera_usage():
    state = camera_usage.MacStreamActivity(own_pid=100)
    state.consume({'eventMessage': 'CMIODeviceStartStream backtrace', 'processID': 200})
    state.consume(event(200, 'StartStream', time='invalid'))
    state.consume({})
    assert not state.other_camera_users(lambda pid, path: True)


def test_native_monitor_detects_an_existing_camera_and_ignores_its_own_stream():
    import json, os, subprocess, sys, time
    processes = []
    own_event = event(os.getpid(), 'StartStream')
    def spawn(args, **kwargs):
        if args[1] == 'stream':
            script = 'import json,time; print(' + repr(json.dumps(own_event)) + ',flush=True); time.sleep(30)'
        else:
            script = 'print(' + repr(json.dumps(own_event)) + ')'
        p = subprocess.Popen([sys.executable, '-u', '-c', script], **kwargs)
        processes.append(p)
        return p
    monitor = camera_usage.MacCameraActivity(popen=spawn, running=lambda: True, alive=lambda pid, path: True)
    try:
        assert monitor(0) is True  # we own no capture, so an active camera belongs to someone else
        monitor.set_capture_active(True)
        assert monitor._ready.wait(3)
        assert monitor(0) is False  # the camera-on flag now includes us; only external stream clients count
    finally:
        monitor.close()
    assert processes and all(p.poll() is not None for p in processes)


def test_coremediaio_reads_running_property_with_the_full_native_signature(monkeypatch):
    import ctypes
    from types import SimpleNamespace
    def size(obj, address, qualifier_size, qualifier, out_size):
        out_size._obj.value = 4
        return 0
    def data(obj, address, qualifier_size, qualifier, buffer_size, used_size, buffer):
        assert buffer_size == 4
        used_size._obj.value = 4
        if obj == 1:
            ctypes.cast(buffer, ctypes.POINTER(ctypes.c_uint32))[0] = 42
        else:
            assert obj == 42 and address._obj.selector == 0x676f6e65  # 'gone'
            ctypes.cast(buffer, ctypes.POINTER(ctypes.c_uint32))[0] = 1
        return 0
    lib = SimpleNamespace(CMIOObjectGetPropertyDataSize=size, CMIOObjectGetPropertyData=data)
    monkeypatch.setattr(camera_usage.ctypes, 'CDLL', lambda path: lib)
    assert camera_usage.cameras_running() is True


def test_live_shared_camera_start_still_pauses_if_history_query_fails():
    import json, subprocess, sys
    processes = []
    def spawn(args, **kwargs):
        script = ('import time; print(' + repr(json.dumps(event(200, 'StartStream'))) +
                  ',flush=True); time.sleep(30)') if args[1] == 'stream' else 'raise SystemExit(1)'
        p = subprocess.Popen([sys.executable, '-u', '-c', script], **kwargs)
        processes.append(p)
        return p
    monitor = camera_usage.MacCameraActivity(popen=spawn, running=lambda: None, alive=lambda pid, path: True)
    monitor.set_capture_active(True)
    try:
        monitor(0)
        assert monitor._ready.wait(3)
        assert monitor(0) is True
    finally:
        monitor.close()
