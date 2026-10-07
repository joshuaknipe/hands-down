import os
import sys

import pytest

from feasibility import coexist, winrt_probe

on_windows = sys.platform == "win32"


@pytest.mark.skipif(on_windows, reason="checks the non-Windows fallback")
def test_shared_capture_is_unavailable_off_windows():
    assert not winrt_probe.winrt_available()
    result = winrt_probe.open_shared()
    assert not result.ok and "only available on Windows" in result.error
    assert coexist.WINRT_SHARED not in coexist.default_backends()


@pytest.mark.skipif(not on_windows, reason="Windows only")
def test_winrt_packages_import_on_windows():
    assert winrt_probe.winrt_available()
    assert coexist.default_backends()[-1] == coexist.WINRT_SHARED


@pytest.mark.skipif(not (on_windows and os.environ.get("CI")), reason="CI runners have no camera")
def test_open_shared_reports_missing_camera_without_raising():
    result = winrt_probe.open_shared()
    assert not result.ok and "no colour camera" in result.error


def test_opener_routes_shared_backend_to_winrt(monkeypatch):
    from handsdown.camera import OpenResult

    monkeypatch.setattr(winrt_probe, "open_shared", lambda: OpenResult("winrt_shared", False, 0.0, error="stub"))
    result = coexist.make_opener(0)(coexist.WINRT_SHARED)
    assert result.error == "stub"
