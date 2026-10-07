import threading
from datetime import datetime

from handsdown.eventlog import EventLog


def test_write_and_read_back(tmp_path):
    log = EventLog(tmp_path / "logs", now=lambda: datetime(2026, 10, 7, 9, 30, 5))
    log.write("state", state="watching")
    log.write("episode", duration_s=2.5, alerted=True, ended="released")
    records = log.read()
    assert records[0] == {"time": "2026-10-07T09:30:05", "kind": "state", "state": "watching"}
    assert records[1]["kind"] == "episode" and records[1]["duration_s"] == 2.5
    assert log.path == tmp_path / "logs" / "events.jsonl"


def test_read_skips_damaged_lines(tmp_path):
    log = EventLog(tmp_path)
    log.write("start")
    with log.path.open("a", encoding="utf-8") as f:
        f.write('{"half a line\n')
    log.write("stop")
    assert [r["kind"] for r in log.read()] == ["start", "stop"]


def test_read_with_no_log_is_empty(tmp_path):
    assert EventLog(tmp_path / "none").read() == []


def test_writes_from_two_threads_do_not_interleave(tmp_path):
    log = EventLog(tmp_path)

    def burst(kind):
        for _ in range(200):
            log.write(kind, detail="x" * 200)

    threads = [threading.Thread(target=burst, args=(k,)) for k in ("a", "b")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(log.read()) == 400
