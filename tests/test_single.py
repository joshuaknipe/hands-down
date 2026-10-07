from handsdown.single import acquire


def test_second_copy_cannot_take_the_lock(tmp_path):
    path = tmp_path / "config" / "running.lock"
    first = acquire(path)
    assert first is not None
    assert acquire(path) is None
    first.release()


def test_lock_is_free_again_after_release(tmp_path):
    path = tmp_path / "running.lock"
    acquire(path).release()
    again = acquire(path)
    assert again is not None
    again.release()
