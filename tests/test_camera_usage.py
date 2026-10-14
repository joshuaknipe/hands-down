from tests.helpers import FakeClock


def test_usage_monitor_polls_at_most_once_per_second_and_uses_camera_index():
    from handsdown.camera_usage import CameraUsageMonitor
    clock = FakeClock(100)
    calls = []
    def check(index):
        calls.append(index)
        return True
    monitor = CameraUsageMonitor(check=check, clock=clock)
    assert monitor(0) is True
    assert monitor(0) is True and calls == [0]
    assert monitor(1) is True and calls == [0, 1]
    clock.now += 2
    assert monitor(1) is True and calls == [0, 1, 1]


def test_usage_check_failure_is_unknown_and_warns_once_until_recovered():
    from handsdown.camera_usage import CameraUsageMonitor
    clock = FakeClock(100)
    warnings = []
    def fail(index):
        raise OSError("unavailable")
    monitor = CameraUsageMonitor(check=fail, clock=clock, warn=warnings.append)
    assert monitor(0) is None
    clock.now += 2
    assert monitor(0) is None and len(warnings) == 1


def test_windows_activity_ignores_self_and_stale_or_finished_entries():
    from handsdown.camera_usage import has_other_windows_camera_user
    running = {r'C:\apps\HandsDown.exe', r'C:\apps\Teams.exe'}
    own = r'C:\apps\HandsDown.exe'
    assert has_other_windows_camera_user([(own, 123, 0)], running, own) is False
    assert has_other_windows_camera_user([(r'C:\apps\Teams.exe', 123, 456)], running, own) is False
    assert has_other_windows_camera_user([(r'C:\gone.exe', 123, 0)], running, own) is False
    assert has_other_windows_camera_user([(r'C:\apps\Teams.exe', 123, 0)], running, own) is True


def test_packaged_windows_activity_requires_a_live_package_process():
    from handsdown.camera_usage import has_other_windows_camera_user
    entries = [('MSTeams_8wekyb3d8bbwe', 123, 0)]
    assert has_other_windows_camera_user(entries, set(), r'C:\HandsDown.exe') is False
    assert has_other_windows_camera_user(entries,
        {r'C:\Program Files\WindowsApps\MSTeams_123_x64__8wekyb3d8bbwe\ms-teams.exe'}, r'C:\HandsDown.exe') is True


def test_windows_activity_accepts_binary_filetime_values():
    from handsdown.camera_usage import has_other_windows_camera_user
    entries = [(r'C:\Teams.exe', (123).to_bytes(8, 'little'), bytes(8))]
    assert has_other_windows_camera_user(entries, {r'C:\Teams.exe'}, r'C:\HandsDown.exe') is True

