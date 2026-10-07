"""Open the camera with each backend for this OS and report how well frames flow."""

import threading
import time

import cv2

from handsdown.camera import Backend, FlowStats, FrameMonitor, OpenCvSource, open_camera, start_reader, stop_reader


def probe_line(name: str, open_seconds: float, size: str, flow: FlowStats, seconds: float) -> str:
    return (
        f"{name:<13} opened in {open_seconds:.1f} s at {size}, {flow.good / seconds:.0f} fps good, "
        f"{flow.black} black, {flow.failed} failed, longest gap {flow.max_gap_s:.1f} s"
    )


def run_probe(camera_index: int, backends: list[Backend], seconds: float, say=print) -> int:
    any_ok = False
    for backend in backends:
        result = open_camera(camera_index, backend)
        if not result.ok:
            say(f"{backend.name:<13} FAILED after {result.seconds:.1f} s: {result.error}")
            continue
        any_ok = True
        capture = result.capture
        size = f"{int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))}"
        source = OpenCvSource(capture)
        monitor = FrameMonitor()
        stop = threading.Event()
        thread = start_reader(source, monitor, stop)
        time.sleep(seconds)
        flow = monitor.snapshot()
        if not stop_reader(thread, stop, source):
            say(f"{backend.name:<13} warning: camera read is stuck; restart before trying again")
        say(probe_line(backend.name, result.seconds, size, flow, seconds))
    return 0 if any_ok else 1
