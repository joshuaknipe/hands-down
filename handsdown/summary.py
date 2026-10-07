"""The summary window: what the event log says about today and the last week.

It runs as its own process (python -m handsdown --summary), like the settings window,
and only reads the log. Counting is kept separate from the window so it can be tested.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from handsdown.eventlog import EventLog
from handsdown.paths import log_dir

REFRESH_MS = 10_000


@dataclass
class DayStats:
    day: date
    episodes: int = 0
    total_s: float = 0.0  # time spent in episodes
    repeats: int = 0
    false_marks: int = 0
    by_hour: list[int] = field(default_factory=lambda: [0] * 24)


def summarise(records: list[dict]) -> dict[date, DayStats]:
    days: dict[date, DayStats] = {}
    for record in records:
        try:
            when = datetime.fromisoformat(record["time"])
        except (KeyError, TypeError, ValueError):
            continue
        stats = days.setdefault(when.date(), DayStats(when.date()))
        kind = record.get("kind")
        if kind == "episode":
            stats.episodes += 1
            stats.total_s += float(record.get("duration_s") or 0.0)
            stats.by_hour[when.hour] += 1
        elif kind == "alert" and record.get("reminder"):
            stats.repeats += 1
        elif kind == "false_alert":
            stats.false_marks += 1
    return days


def recent_days(days: dict[date, DayStats], today: date, count: int = 7) -> list[DayStats]:
    """The last `count` days, newest first, with quiet days included."""
    wanted = [today - timedelta(days=n) for n in range(count)]
    return [days.get(day, DayStats(day)) for day in wanted]


def format_duration(seconds: float) -> str:
    seconds = round(seconds)
    if seconds < 60:
        return f"{seconds} s"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} min"
    return f"{minutes // 60} h {minutes % 60} min"


def run_summary_window(log: EventLog | None = None, now=datetime.now) -> int:
    import tkinter as tk
    from tkinter import ttk

    log = log or EventLog(log_dir())
    root = tk.Tk()
    root.title("Hands Down summary")
    root.resizable(False, False)
    frame = ttk.Frame(root, padding=16)
    frame.grid(sticky="nsew")

    headline = ttk.Label(frame, font=("TkDefaultFont", 13, "bold"))
    headline.grid(row=0, column=0, sticky="w")
    details = ttk.Label(frame)
    details.grid(row=1, column=0, sticky="w", pady=(4, 12))

    chart_w, chart_h = 480, 110
    chart = tk.Canvas(frame, width=chart_w, height=chart_h, highlightthickness=0)
    chart.grid(row=2, column=0, sticky="w")
    ttk.Label(frame, text="Today, by hour", foreground="grey").grid(row=3, column=0, sticky="w", pady=(2, 12))

    table = ttk.Treeview(frame, columns=("day", "episodes", "time", "marks"), show="headings", height=7)
    for column, title, width in (("day", "Day", 130), ("episodes", "Episodes", 90), ("time", "Time", 110),
                                 ("marks", "Marked not me", 120)):
        table.heading(column, text=title)
        table.column(column, width=width, anchor="w")
    table.grid(row=4, column=0, sticky="w")
    ttk.Button(frame, text="Close", command=root.destroy).grid(row=5, column=0, sticky="e", pady=(12, 0))

    def refresh() -> None:
        today = now().date()
        days = recent_days(summarise(log.read()), today)
        stats = days[0]
        plural = "" if stats.episodes == 1 else "s"
        headline.config(text=f"Today: {stats.episodes} episode{plural}, {format_duration(stats.total_s)} in total")
        details.config(text=f"{stats.repeats} repeat alerts   ·   {stats.false_marks} marked \"That wasn't me\"")

        chart.delete("all")
        peak = max(stats.by_hour) or 1
        bar_w = chart_w / 24
        for hour, count in enumerate(stats.by_hour):
            x0 = hour * bar_w + 2
            if count:
                height = (chart_h - 20) * count / peak
                chart.create_rectangle(x0, chart_h - 16 - height, x0 + bar_w - 4, chart_h - 16,
                                       fill="#58a6a0", outline="")
            if hour % 3 == 0:
                chart.create_text(x0, chart_h - 2, text=f"{hour:02d}", anchor="sw", fill="grey")

        table.delete(*table.get_children())
        for day in days:
            label = "Today" if day.day == today else day.day.strftime("%a %d %b")
            table.insert("", "end", values=(label, day.episodes, format_duration(day.total_s), day.false_marks))
        root.after(REFRESH_MS, refresh)

    refresh()
    root.mainloop()
    return 0
