"""Guided test of whether Hands Down and the Teams desktop app can use the camera at the same time.

Each backend is tried in both launch orders. The person at the laptop starts and leaves
Teams meetings when prompted and says whether their own video shows in Teams.
"""

import threading
import time
from dataclasses import asdict, dataclass
from typing import Callable

from handsdown.camera import (
    FlowStats, FrameMonitor, OpenCvSource, OpenResult,
    backend_by_name, backends_for_platform, open_camera, start_reader, stop_reader,
)

ORDERS = ("app_first", "teams_first")
OBSERVE_SECONDS = 15.0  # how long both apps run together before asking about Teams
MIN_GOOD_FRAMES = 30  # Hands Down must keep getting real frames...
MAX_GAP_S = 3.0  # ...with no stall longer than this
WINRT_SHARED = "winrt_shared"

TEAMS_START = "Start a Teams 'Meet now' meeting (Calendar > Meet now) with your camera on."
MULTI_APP_QUESTION = (
    "Open Settings > Bluetooth & devices > Cameras and choose your webcam. If there is a setting about "
    "letting more than one app use the camera, type its name and whether it is on or off; otherwise type 'none': "
)


@dataclass
class TrialResult:
    backend: str
    order: str
    app_opened: bool
    open_seconds: float
    open_error: str
    app_flow: FlowStats | None
    teams_video_ok: bool | None  # None when Hands Down could not start the trial

    @property
    def app_kept_frames(self) -> bool:
        flow = self.app_flow
        return flow is not None and flow.good >= MIN_GOOD_FRAMES and flow.max_gap_s <= MAX_GAP_S

    @property
    def coexisted(self) -> bool:
        return self.app_opened and self.app_kept_frames and self.teams_video_ok is True

    def to_dict(self) -> dict:
        return asdict(self) | {"app_kept_frames": self.app_kept_frames, "coexisted": self.coexisted}


def ask_yes_no(ask: Callable[[str], str], question: str) -> bool:
    while True:
        answer = ask(f"{question} [y/n] ").strip().lower()
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False


def run_trial(backend: str, order: str, opener: Callable[[str], OpenResult], ask, say,
              observe_seconds: float = OBSERVE_SECONDS, sleep=time.sleep,
              monitor_factory=FrameMonitor) -> TrialResult:
    say(f"\n=== {backend}, {order.replace('_', ' ')} ===")
    if order == "teams_first":
        ask(f"{TEAMS_START} Press Enter when your video is showing in Teams.")
    else:
        ask("Make sure Teams is not using the camera (leave any meeting). Press Enter to continue.")

    result = opener(backend)
    if not result.ok:
        say(f"Hands Down could not open the camera: {result.error}")
        teams_ok = None
        if order == "teams_first":
            teams_ok = ask_yes_no(ask, "Is your own video still showing in Teams?")
            ask("Leave the Teams meeting, then press Enter.")
        return TrialResult(backend, order, False, result.seconds, result.error, None, teams_ok)

    say(f"Hands Down opened the camera in {result.seconds:.1f} s.")
    monitor = monitor_factory()
    stop = threading.Event()
    thread = start_reader(result.capture, monitor, stop)
    if order == "app_first":
        ask(f"Hands Down is now using the camera. {TEAMS_START} "
            "Press Enter once Teams has had a few seconds to show your video.")
    say(f"Watching both apps for {observe_seconds:.0f} s...")
    sleep(observe_seconds)
    teams_ok = ask_yes_no(ask, "Is your own video showing in Teams?")
    flow = monitor.snapshot()
    if not stop_reader(thread, stop, result.capture):
        say("Warning: Hands Down's camera read is stuck. If the next backend fails to open, restart the tool.")
    ask("Leave the Teams meeting, then press Enter.")
    return TrialResult(backend, order, True, result.seconds, "", flow, teams_ok)


def coexisting_backends(trials: list[TrialResult]) -> list[str]:
    """Backends that coexisted with Teams in both launch orders, in the order tried."""
    names = list(dict.fromkeys(t.backend for t in trials))
    return [name for name in names
            if all(any(t.backend == name and t.order == order and t.coexisted for t in trials) for order in ORDERS)]


def conclusion(trials: list[TrialResult]) -> str:
    both = coexisting_backends(trials)
    opencv = [name for name in both if name != WINRT_SHARED]
    if opencv:
        return (f"OpenCV ({', '.join(opencv)}) works alongside Teams in both launch orders: "
                "no special handling needed beyond camera-busy retries.")
    if WINRT_SHARED in both:
        return ("Only Windows shared capture works alongside Teams in both launch orders: "
                "switch the Windows camera module to WinRT MediaCapture.")
    return ("No backend worked alongside Teams in both launch orders: "
            "Hands Down must release the camera for calls (pause for call).")


def summary_lines(trials: list[TrialResult]) -> list[str]:
    lines = ["", f"{'backend':<13} {'order':<12} {'result':<6} details"]
    for t in trials:
        if t.app_opened:
            details = (f"Hands Down frames: {t.app_flow.good} good, longest gap {t.app_flow.max_gap_s:.1f} s; "
                       f"Teams video: {'yes' if t.teams_video_ok else 'no'}")
        else:
            details = f"Hands Down did not open: {t.open_error}"
        lines.append(f"{t.backend:<13} {t.order:<12} {'OK' if t.coexisted else 'FAIL':<6} {details}")
    return lines


def run_session(backends: list[str], opener, ask, say, observe_seconds: float = OBSERVE_SECONDS,
                sleep=time.sleep, monitor_factory=FrameMonitor) -> dict:
    setting = ask(MULTI_APP_QUESTION).strip()
    trials = [run_trial(backend, order, opener, ask, say, observe_seconds, sleep, monitor_factory)
              for backend in backends for order in ORDERS]
    for line in summary_lines(trials):
        say(line)
    verdict = conclusion(trials)
    say(f"\nConclusion: {verdict}")
    return {
        "windows_multi_app_setting": setting,
        "trials": [t.to_dict() for t in trials],
        "conclusion": verdict,
    }


def make_opener(camera_index: int) -> Callable[[str], OpenResult]:
    def opener(name: str) -> OpenResult:
        if name == WINRT_SHARED:
            from feasibility import winrt_probe

            return winrt_probe.open_shared()
        result = open_camera(camera_index, backend_by_name(name))
        if result.ok:
            result.capture = OpenCvSource(result.capture)
        return result

    return opener


def default_backends() -> list[str]:
    from feasibility.winrt_probe import winrt_available

    names = [backend.name for backend in backends_for_platform()]
    if winrt_available():
        names.append(WINRT_SHARED)
    return names
