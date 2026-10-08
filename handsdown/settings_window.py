"""The settings window. It runs as its own process (python -m handsdown --settings) so tkinter
never shares a thread with the tray icon, and saves to the settings file the app watches."""

import sys
from dataclasses import replace
from pathlib import Path
from typing import Callable

from handsdown import startup
from handsdown.alerts import play_chime
from handsdown.paths import settings_path
from handsdown.settings import LIMITS, Settings, clamp, load_settings, save_settings

REMINDER_CHOICES = {
    "Never": 0.0, "Continuously": 1.5, "Every 3 seconds": 3.0, "Every 5 seconds": 5.0, "Every 10 seconds": 10.0,
    "Every 15 seconds": 15.0, "Every 30 seconds": 30.0, "Every minute": 60.0,
}
RELEASE_CHOICES = {"2 seconds": 2.0, "3 seconds": 3.0, "5 seconds": 5.0, "10 seconds": 10.0, "30 seconds": 30.0}
ZONE_SLIDERS = ("zone_margin", "zone_above", "zone_below", "chin_cutout")
SOUND_CHOICES = {"Chime": "chime", "Bell": "bell", "Soft knock": "knock", "Rising": "rising", "Low tone": "low",
                 "Buzz": "buzz", "Beeps": "beeps", "Warble": "warble", "Honk": "honk"}
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
        "screen_border": settings.screen_border,
        "dwell_s": settings.dwell_s,
        "reminder": _closest(REMINDER_CHOICES, settings.reminder_s),
        "release": _closest(RELEASE_CHOICES, settings.release_s),
        **{name: getattr(settings, name) for name in ZONE_SLIDERS},
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
        screen_border=bool(values["screen_border"]),
        dwell_s=round(float(values["dwell_s"]), 2),
        reminder_s=REMINDER_CHOICES[values["reminder"]],
        release_s=RELEASE_CHOICES[values["release"]],
        **{name: round(float(values[name]), 2) for name in ZONE_SLIDERS},
        pause_when_locked=bool(values["pause_when_locked"]),
        start_with_windows=bool(values["start_with_windows"]),
        camera_index=int(values["camera_index"]),
    ))


class AutoSaver:
    """Saves the form whenever it changes, so the running app picks each change up straight away."""

    def __init__(self, path: Path, base: Settings, save=save_settings,
                 set_startup: Callable[[bool], bool] | None = None):
        self._path = path
        self._save = save
        self._set_startup = set_startup
        self._last = base
        self._startup_requested = base.start_with_windows
        self._startup_state = base.start_with_windows

    @property
    def starts_with_windows(self) -> bool:
        return self._startup_state

    def update(self, values: dict) -> Settings:
        new = settings_from_form(values, self._last)
        if new.start_with_windows != self._startup_requested:  # only touch the registry when the box changes
            self._startup_requested = new.start_with_windows
            self._startup_state = (self._set_startup(new.start_with_windows) if self._set_startup
                                   else new.start_with_windows)
        new = replace(new, start_with_windows=self._startup_state)
        if new != self._last:
            self._save(self._path, new)
            self._last = new
        return new


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
    screen_border = tk.BooleanVar(value=values["screen_border"])
    dwell = tk.DoubleVar(value=values["dwell_s"])
    reminder = tk.StringVar(value=values["reminder"])
    zone = {name: tk.DoubleVar(value=values[name]) for name in ZONE_SLIDERS}
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
    add("Red border round the screen", ttk.Checkbutton(frame, variable=screen_border))
    hint("From the alert until the hand moves away. Seen by others if you share your screen")
    def slider(label: str, variable: tk.DoubleVar, low: float, high: float, fmt: str) -> None:
        shown = ttk.Label(frame, text=fmt.format(variable.get()))
        add(label, ttk.Scale(frame, from_=low, to=high, variable=variable, length=180,
                             command=lambda _value: shown.config(text=fmt.format(variable.get()))))
        shown.grid(row=row - 1, column=2, sticky="w")

    slider("Wait before alerting", dwell, 0.2, 3.0, "{:.1f} s")
    add("Repeat the alert", ttk.Combobox(frame, textvariable=reminder, state="readonly",
                                         values=list(REMINDER_CHOICES), width=18))
    hint("Repeats stop as soon as the hand moves away")
    add("Next alert needs hands away for", ttk.Combobox(frame, textvariable=release, state="readonly",
                                                        values=list(RELEASE_CHOICES), width=18))
    hint("A shorter break counts as the same touch")
    slider("Zone to the sides", zone["zone_margin"], *LIMITS["zone_margin"], "{:.2f} face widths")
    slider("Zone above the face", zone["zone_above"], *LIMITS["zone_above"], "{:.2f} face heights")
    slider("Zone below the chin", zone["zone_below"], *LIMITS["zone_below"], "{:.2f} face heights")
    slider("Ignored chin area", zone["chin_cutout"], *LIMITS["chin_cutout"], "{:.1f}x")
    hint("Set to 0 to count the chin and mouth too")
    add("Pause while the screen is locked", ttk.Checkbutton(frame, variable=pause_when_locked))
    if startup.startup_label():
        add(startup.startup_label(), ttk.Checkbutton(frame, variable=start))
    add("Camera number", ttk.Spinbox(frame, from_=0, to=9, textvariable=camera, width=5))

    saver = AutoSaver(path, base, set_startup=startup.set_start_at_login if startup.startup_label() else None)
    pending = [None]

    def save_now() -> None:
        pending[0] = None
        try:
            saver.update({
                "chime": chime.get(), "sound": sound.get(), "volume": volume.get(),
                "notification": notification.get(), "screen_border": screen_border.get(), "dwell_s": dwell.get(),
                "reminder": reminder.get(),
                "release": release.get(), "pause_when_locked": pause_when_locked.get(),
                **{name: variable.get() for name, variable in zone.items()},
                "start_with_windows": start.get(),
                "camera_index": camera.get(),
            })
        except (tk.TclError, ValueError, KeyError):
            pass  # a half-typed number: save once it is valid
        if start.get() != saver.starts_with_windows:
            start.set(saver.starts_with_windows)  # registering can be refused, e.g. when run from source

    def changed(*_args) -> None:
        if pending[0] is not None:
            root.after_cancel(pending[0])
        pending[0] = root.after(300, save_now)  # wait until a slider drag settles

    for variable in (chime, sound, volume, notification, screen_border, dwell, reminder, release, pause_when_locked,
                     start, camera, *zone.values()):
        variable.trace_add("write", changed)

    def close() -> None:
        if pending[0] is not None:
            root.after_cancel(pending[0])
            save_now()
        root.destroy()

    hint_row = row
    ttk.Label(frame, text="Changes are saved as you make them", foreground="grey").grid(
        row=hint_row, column=0, columnspan=2, sticky="w", pady=(12, 0))
    ttk.Button(frame, text="Close", command=close).grid(row=hint_row, column=2, sticky="e", pady=(12, 0))
    root.protocol("WM_DELETE_WINDOW", close)
    root.mainloop()
    return 0
