import threading

import pytest

from feasibility import coexist
from feasibility.coexist import TrialResult, ask_yes_no, conclusion, run_session, run_trial
from handsdown.camera import FlowStats, OpenResult
from tests.helpers import ScriptedAsk

SMOOTH = FlowStats(good=400, black=0, failed=0, max_gap_s=0.1)
STALLED = FlowStats(good=400, black=0, failed=20, max_gap_s=6.0)


class FakeSource:
    def __init__(self):
        self.closed = False

    def read_status(self):
        threading.Event().wait(0.001)
        return "good"

    def close(self):
        self.closed = True


class StubMonitor:
    def __init__(self, stats):
        self.stats = stats

    def record(self, status):
        pass

    def snapshot(self):
        return self.stats


def opener_for(ok_backends):
    sources = {}

    def opener(name):
        if name in ok_backends:
            sources[name] = FakeSource()
            return OpenResult(name, True, 0.4, capture=sources[name])
        return OpenResult(name, False, 1.2, error="camera did not open")

    return opener, sources


def trial(backend, order, answers, ok_backends=("dshow",), flow=SMOOTH):
    opener, sources = opener_for(ok_backends)
    ask = ScriptedAsk(answers)
    result = run_trial(backend, order, opener, ask, say=lambda s: None, observe_seconds=0,
                       sleep=lambda s: None, monitor_factory=lambda: StubMonitor(flow))
    assert ask.answers == [], "not every scripted answer was used"
    return result, ask, sources


def test_app_first_success_coexists_and_closes_the_camera():
    result, ask, sources = trial("dshow", "app_first", ["", "", "y", ""])
    assert result.coexisted and result.app_kept_frames and result.teams_video_ok
    assert "not using the camera" in ask.prompts[0]
    assert "Hands Down is now using the camera" in ask.prompts[1]
    assert sources["dshow"].closed


def test_teams_first_success_coexists():
    result, ask, _ = trial("dshow", "teams_first", ["", "y", ""])
    assert result.coexisted
    assert "Meet now" in ask.prompts[0]


def test_teams_first_when_app_cannot_open():
    result, _, _ = trial("msmf", "teams_first", ["", "y", ""])
    assert not result.app_opened and result.teams_video_ok is True and not result.coexisted
    assert result.open_error == "camera did not open" and result.app_flow is None


def test_app_first_when_app_cannot_open_stops_early():
    result, ask, _ = trial("msmf", "app_first", [""])
    assert not result.app_opened and result.teams_video_ok is None


def test_teams_video_missing_is_not_coexisting():
    result, _, _ = trial("dshow", "app_first", ["", "", "n", ""])
    assert result.app_kept_frames and not result.coexisted


def test_app_frames_stalling_is_not_coexisting():
    result, _, _ = trial("dshow", "app_first", ["", "", "y", ""], flow=STALLED)
    assert not result.app_kept_frames and not result.coexisted


def test_too_few_good_frames_is_not_coexisting():
    result, _, _ = trial("dshow", "app_first", ["", "", "y", ""], flow=FlowStats(good=5, max_gap_s=0.1))
    assert not result.coexisted


def test_ask_yes_no_reprompts_until_answered():
    ask = ScriptedAsk(["maybe", "", " Y "])
    assert ask_yes_no(ask, "Video?") is True
    assert len(ask.prompts) == 3


def result_for(backend, order, ok):
    return TrialResult(backend, order, ok, 0.3, "", SMOOTH if ok else None, ok)


def test_conclusion_prefers_opencv_when_it_coexists_both_ways():
    trials = [result_for("dshow", o, True) for o in coexist.ORDERS] + [result_for("msmf", "app_first", False)]
    assert "no special handling" in conclusion(trials) and "dshow" in conclusion(trials)


def test_conclusion_one_order_is_not_enough():
    trials = [result_for("dshow", "app_first", True), result_for("dshow", "teams_first", False)]
    assert "release the camera" in conclusion(trials)


def test_conclusion_when_only_shared_capture_works():
    trials = [result_for("dshow", o, False) for o in coexist.ORDERS]
    trials += [result_for(coexist.WINRT_SHARED, o, True) for o in coexist.ORDERS]
    assert "MediaCapture" in conclusion(trials)


def test_trial_result_dict_includes_derived_fields():
    data = result_for("dshow", "app_first", True).to_dict()
    assert data["coexisted"] is True and data["app_kept_frames"] is True
    assert data["app_flow"]["good"] == 400


def test_session_runs_every_backend_in_both_orders():
    opener, _ = opener_for(("dshow",))
    answers = ["off"]
    answers += ["", "", "y", ""]  # dshow, Hands Down first
    answers += ["", "y", ""]  # dshow, Teams first
    answers += [""]  # msmf, Hands Down first: cannot open
    answers += ["", "y", ""]  # msmf, Teams first: cannot open
    ask = ScriptedAsk(answers)
    report = run_session(["dshow", "msmf"], opener, ask, say=lambda s: None, observe_seconds=0,
                         sleep=lambda s: None, monitor_factory=lambda: StubMonitor(SMOOTH))
    assert ask.answers == []
    assert report["windows_multi_app_setting"] == "off"
    assert [(t["backend"], t["order"]) for t in report["trials"]] == [
        ("dshow", "app_first"), ("dshow", "teams_first"), ("msmf", "app_first"), ("msmf", "teams_first"),
    ]
    assert "dshow" in report["conclusion"]


def test_default_backends_on_this_platform_are_opencv_names():
    names = coexist.default_backends()
    assert names and all(name in ("dshow", "msmf", "avfoundation", "any", coexist.WINRT_SHARED) for name in names)
