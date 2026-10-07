"""The settings window. It runs as its own process (python -m handsdown --settings) so tkinter
never shares a thread with the tray icon, and saves to the settings file the app watches."""

import sys
from dataclasses import replace
from pathlib import Path

from handsdown import startup
from handsdown.alerts import play_chime
from handsdown.paths import settings_path
from handsdown.settings import Settings, clamp, load_settings, save_settings

REMINDER_CHOICES = {
    "Never": 0.0, "Every 3 seconds": 3.0, "Every 5 seconds": 5.0, "Every 10 seconds": 10.0,
    "Every 15 seconds": 15.0, "Every 30 seconds": 30.0, "Every minute": 60.0,
}
RELEASE_CHOICES = {"2 seconds": 2.0, "3 seconds": 3.0, "5 seconds": 5.0, "10 seconds": 10.0, "30 seconds": 30.0}
ZONE_CHOICES = {"Small": 0.3, "Medium": 0.5, "Large": 0.8}
SOUND_CHOICES = {"Chime": "chime", "Bell": "bell", "Soft knock": "knock", "Rising": "rising"}
VOLUME_CHOICES = {"Quiet": "quiet", "Medium": "medium", "Normal": "normal"}


def _closest(choices: dict, value: float) -> str:
    return min(choices, key=lambda label: abs(choices[label] - value))


def _label(choices: dict, value: str) -> str:
    return next((label for label, v in choices.items() if v == value), next(iter(choices)))


def form_values(settings: Settings) -> dict:
    return {
        "chime": settings.chime,
        "sound": _label(SOUND_CHOICES, settings.sound),
        "volume": _label(VOLUME_CHOICES, settings.volume),
        "notification": settings.notification,
        "dwell_s": settings.dwell_s,
        "reminder": _closest(REMINDER_CHOICES, settings.reminder_s),
        "release": _closest(RELEASE_CHOICES, settings.release_s),
        "zone": _closest(ZONE_CHOICES, settings.zone_margin),
        "pause_when_locked": settings.pause_when_locked,
        "start_with_windows": settings.start_with_windows,
        "camera_index": settings.camera_index,
    }


def settings_from_form(values: dict, base: Settings) -> Settings:
    return clamp(replace(
        base,
        chime=bool(values["chime"]),
        sound=SOUND_CHOICES[values["sound"]],
        volume=VOLUME_CHOICES[values["volume"]],
        notification=bool(values["notification"]),
        dwell_s=round(float(values["dwell_s"]), 2),
        reminder_s=REMINDER_CHOICES[values["reminder"]],
        release_s=RELEASE_CHOICES[values["release"]],
        zone_margin=ZONE_CHOICES[values["zone"]],
        pause_when_locked=bool(values["pause_when_locked"]),
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
    sound = tk.StringVar(value=values["sound"])
    volume = tk.StringVar(value=values["volume"])
    release = tk.StringVar(value=values["release"])
    pause_when_locked = tk.BooleanVar(value=values["pause_when_locked"])
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

    def hint(text: str) -> None:
        nonlocal row
        ttk.Label(frame, text=text, foreground="grey").grid(row=row, column=1, columnspan=2, sticky="w", pady=(0, 6))
        row += 1

    add("Alert sound", ttk.Checkbutton(frame, variable=chime))
    add("Sound", ttk.Combobox(frame, textvariable=sound, state="readonly", values=list(SOUND_CHOICES), width=18))
    add("Volume", ttk.Combobox(frame, textvariable=volume, state="readonly", values=list(VOLUME_CHOICES), width=18))

    def test_sound() -> None:
        try:
            play_chime(SOUND_CHOICES[sound.get()], VOLUME_CHOICES[volume.get()])
        except Exception:
            pass  # a missing audio device should not close the settings window

    ttk.Button(frame, text="Play", command=test_sound).grid(row=row - 1, column=2, sticky="w")
    add("Notification", ttk.Checkbutton(frame, variable=notification))
    dwell_label = ttk.Label(frame, text=f"{dwell.get():.1f} s")
    slider = ttk.Scale(frame, from_=0.2, to=3.0, variable=dwell, length=180,
                       command=lambda _value: dwell_label.config(text=f"{dwell.get():.1f} s"))
    add("Wait before alerting", slider)
    dwell_label.grid(row=row - 1, column=2, sticky="w")
    add("Repeat the alert", ttk.Combobox(frame, textvariable=reminder, state="readonly",
                                         values=list(REMINDER_CHOICES), width=18))
    hint("One alert per touch unless set")
    add("Next alert needs hands away for", ttk.Combobox(frame, textvariable=release, state="readonly",
                                                        values=list(RELEASE_CHOICES), width=18))
    hint("A shorter break counts as the same touch")
    add("Area around the head", ttk.Combobox(frame, textvariable=zone, state="readonly",
                                             values=list(ZONE_CHOICES), width=18))
    add("Pause while the screen is locked", ttk.Checkbutton(frame, variable=pause_when_locked))
    if sys.platform == "win32":
        add("Start with Windows", ttk.Checkbutton(frame, variable=start))
    add("Camera number", ttk.Spinbox(frame, from_=0, to=9, textvariable=camera, width=5))

    def save() -> None:
        new = settings_from_form({
            "chime": chime.get(), "sound": sound.get(), "volume": volume.get(),
            "notification": notification.get(), "dwell_s": dwell.get(), "reminder": reminder.get(),
            "release": release.get(), "zone": zone.get(), "pause_when_locked": pause_when_locked.get(),
            "start_with_windows": start.get(),
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
