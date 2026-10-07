from handsdown import screenlock


def test_unknown_platform_is_never_locked():
    assert screenlock.is_screen_locked(platform="linux") is False


def test_a_failing_check_counts_as_unlocked():
    def broken():
        raise OSError("no session")

    assert screenlock.is_screen_locked(platform="win32", checks={"win32": broken}) is False


def test_the_platform_check_decides():
    assert screenlock.is_screen_locked(platform="darwin", checks={"darwin": lambda: True}) is True


def test_this_machine_gives_an_answer():
    assert screenlock.is_screen_locked() in (True, False)
