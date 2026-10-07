"""The settings window. It runs as its own process (python -m handsdown --settings) so tkinter
never shares a thread with the tray icon, and saves to the settings file the app watches."""

import sys
from dataclasses import replace
from pathlib import Path

from handsdown import startup
from handsdown.paths import settings_path
from handsdown.settings import Settings, clamp, load_settings, save_settings

REMINDER_CHOICES = {"Off": 0.0, "Every 30 seconds": 30.0, "Every minute": 60.0, "Every 2 minutes": 120.0}
ZONE_CHOICES = {"Small": 0.3, "Medium": 0.5, "Large": 0.8}


def _closest(choices: dict, value: float) -> str:
    return min(choices, key=lambda label: abs(choices[label] - value))


def form_values(settings: Settings) -> dict:
    return {
        "chime": settings.chime,
        "notification": settings.notification,
        "dwell_s": settings.dwell_s,
        "reminder": _closest(REMINDER_CHOICES, settings.reminder_s),
        "zone": _closest(ZONE_CHOICES, settings.zone_margin),
        "start_with_windows": settings.start_with_windows,
        "camera_index": settings.camera_index,
    }


def settings_from_form(values: dict, base: Settings) -> Settings:
    return clamp(replace(
        base,
        chime=bool(values["chime"]),
        notification=bool(values["notification"]),
        dwell_s=round(float(values["dwell_s"]), 2),
        reminder_s=REMINDER_CHOICES[values["reminder"]],
        zone_margin=ZONE_CHOICES[values["zone"]],
        start_with_windows=bool(values["start_with_windows"]),
        camera_index=int(values["camera_index"]),
    ))


def run_settings_window(path: Path | None = None) -> int:
    import tkinter as tk
    from tkinter import ttk

    path = path or settings_path()
    base = load_settings(path)
    values = form_values(base)

    root = tk.Tk()
    root.title("Hands Down settings")
    root.resizable(False, False)
    frame = ttk.Frame(root, padding=16)
    frame.grid(sticky="nsew")

    chime = tk.BooleanVar(value=values["chime"])
    notification = tk.BooleanVar(value=values["notification"])
    dwell = tk.DoubleVar(value=values["dwell_s"])
    reminder = tk.StringVar(value=values["reminder"])
    zone = tk.StringVar(value=values["zone"])
    start = tk.BooleanVar(value=values["start_with_windows"])
    camera = tk.IntVar(value=values["camera_index"])

    row = 0

    def add(label: str, widget) -> None:
        nonlocal row
        ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=4, padx=(0, 12))
        widget.grid(row=row, column=1, sticky="w", pady=4)
        row += 1

    add("Alert sound", ttk.Checkbutton(frame, variable=chime))
    add("Notification", ttk.Checkbutton(frame, variable=notification))
    dwell_label = ttk.Label(frame, text=f"{dwell.get():.1f} s")
    slider = ttk.Scale(frame, from_=0.2, to=3.0, variable=dwell, length=180,
                       command=lambda _value: dwell_label.config(text=f"{dwell.get():.1f} s"))
    add("Wait before alerting", slider)
    dwell_label.grid(row=row - 1, column=2, sticky="w")
    add("Repeat while it continues", ttk.Combobox(frame, textvariable=reminder, state="readonly",
                                                  values=list(REMINDER_CHOICES), width=18))
    add("Area around the head", ttk.Combobox(frame, textvariable=zone, state="readonly",
                                             values=list(ZONE_CHOICES), width=18))
    if sys.platform == "win32":
        add("Start with Windows", ttk.Checkbutton(frame, variable=start))
    add("Camera number", ttk.Spinbox(frame, from_=0, to=9, textvariable=camera, width=5))

    def save() -> None:
        new = settings_from_form({
            "chime": chime.get(), "notification": notification.get(), "dwell_s": dwell.get(),
            "reminder": reminder.get(), "zone": zone.get(), "start_with_windows": start.get(),
            "camera_index": camera.get(),
        }, base)
        if sys.platform == "win32":
            new = replace(new, start_with_windows=startup.set_start_with_windows(new.start_with_windows))
        save_settings(path, new)
        root.destroy()

    buttons = ttk.Frame(frame)
    buttons.grid(row=row, column=0, columnspan=3, sticky="e", pady=(12, 0))
    ttk.Button(buttons, text="Cancel", command=root.destroy).grid(row=0, column=0, padx=(0, 8))
    ttk.Button(buttons, text="Save", command=save).grid(row=0, column=1)
    root.mainloop()
    return 0
