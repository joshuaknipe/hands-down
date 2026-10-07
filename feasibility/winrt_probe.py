"""Best-effort probe of Windows shared camera access (MediaCapture in SharedReadOnly mode) via pywinrt.

Shared mode lets Hands Down read frames while another app, such as Teams, controls the camera.
Windows-only and untestable on the Mac, so it stays small and never raises: any failure
becomes the error text of an OpenResult, and the coexist session carries on.
"""

import asyncio
import sys
import time

from handsdown.camera import OpenResult

BACKEND = "winrt_shared"


def winrt_available() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import winrt.windows.media.capture  # noqa: F401
        import winrt.windows.media.capture.frames  # noqa: F401
    except ImportError:
        return False
    return True


class WinrtSharedSource:
    def __init__(self, capture, reader):
        self._capture = capture
        self._reader = reader

    def read_status(self) -> str | None:
        frame = self._reader.try_acquire_latest_frame()
        if frame is None:
            return None  # no new frame since the last call
        try:
            return "good" if frame.video_media_frame is not None else "failed"
        finally:
            frame.close()

    def close(self) -> None:
        try:
            asyncio.run(_stop(self._reader))
        finally:
            self._capture.close()


async def _stop(reader) -> None:
    await reader.stop_async()


async def _open():
    from winrt.windows.media.capture import (
        MediaCapture, MediaCaptureInitializationSettings, MediaCaptureMemoryPreference,
        MediaCaptureSharingMode, StreamingCaptureMode,
    )
    from winrt.windows.media.capture.frames import (
        MediaFrameReaderStartStatus, MediaFrameSourceGroup, MediaFrameSourceKind,
    )
    import winrt.windows.foundation.collections  # noqa: F401  (lets frame_sources behave as a mapping)

    groups = await MediaFrameSourceGroup.find_all_async()
    group = next((g for g in groups
                  if any(info.source_kind == MediaFrameSourceKind.COLOR for info in g.source_infos)), None)
    if group is None:
        raise RuntimeError("no colour camera found")

    settings = MediaCaptureInitializationSettings()
    settings.source_group = group
    settings.sharing_mode = MediaCaptureSharingMode.SHARED_READ_ONLY
    settings.streaming_capture_mode = StreamingCaptureMode.VIDEO
    settings.memory_preference = MediaCaptureMemoryPreference.CPU
    capture = MediaCapture()
    await capture.initialize_async(settings)

    source = next((s for s in capture.frame_sources.values()
                   if s.info.source_kind == MediaFrameSourceKind.COLOR), None)
    if source is None:
        capture.close()
        raise RuntimeError("camera has no colour stream")
    reader = await capture.create_frame_reader_async(source)
    status = await reader.start_async()
    if status != MediaFrameReaderStartStatus.SUCCESS:
        capture.close()
        raise RuntimeError(f"frame reader did not start: {status.name}")
    return capture, reader


def open_shared(clock=time.monotonic) -> OpenResult:
    start = clock()
    if not winrt_available():
        return OpenResult(BACKEND, False, 0.0, error="shared capture is only available on Windows with pywinrt installed")
    try:
        capture, reader = asyncio.run(_open())
    except Exception as exc:
        return OpenResult(BACKEND, False, clock() - start, error=f"{type(exc).__name__}: {exc}")
    return OpenResult(BACKEND, True, clock() - start, capture=WinrtSharedSource(capture, reader))
