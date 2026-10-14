"""The settings window. It runs as its own process (python -m handsdown --settings) so tkinter
never shares a thread with the tray icon, and saves to the settings file the app watches."""

import sys
from dataclasses import replace
from pathlib import Path
from typing import Callable

from handsdown import startup
from handsdown.border import Border, EFFECT_FIELDS
from handsdown.commands import border_command
from handsdown.alerts import play_chime
from handsdown.paths import settings_path
from handsdown.settings import LIMITS, Settings, clamp, load_settings, save_settings

REMINDER_CHOICES = {
    "Never": 0.0, "Continuously": 1.5, "Every 3 seconds": 3.0, "Every 5 seconds": 5.0, "Every 10 seconds": 10.0,
    "Every 15 seconds": 15.0, "Every 30 seconds": 30.0, "Every minute": 60.0,
}
RELEASE_CHOICES = {"2 seconds": 2.0, "3 seconds": 3.0, "5 seconds": 5.0, "10 seconds": 10.0, "30 seconds": 30.0}
SCREEN_FIELDS = EFFECT_FIELDS[1:]
TEXT_POSITION_CHOICES = {"Top left": "top-left", "Top center": "top-center", "Top right": "top-right",
                         "Middle left": "middle-left", "Center": "center", "Middle right": "middle-right",
                         "Bottom left": "bottom-left", "Bottom center": "bottom-center", "Bottom right": "bottom-right"}
ZONE_SLIDERS = ("zone_margin", "zone_above", "zone_below", "chin_cutout")
SOUND_CHOICES = {"Chime": "chime", "Bell": "bell", "Soft knock": "knock", "Rising": "rising", "Low tone": "low",
                 "Buzz": "buzz", "Beeps": "beeps", "Warble": "warble", "Honk": "honk"}


def _closest(choices: dict, value: float) -> str:
    return min(choices, key=lambda label: abs(choices[label] - value))


def _label(choices: dict, value: str) -> str:
    return next((label for label, v in choices.items() if v == value), next(iter(choices)))


def form_values(settings: Settings) -> dict:
    return {
        "chime": settings.chime,
        "sound": _label(SOUND_CHOICES, settings.sound),
        "volume": settings.volume,
        "notification": settings.notification,
        "screen_border": settings.screen_border,
        **{name: getattr(settings, name) for name in SCREEN_FIELDS},
        "text_position": _label(TEXT_POSITION_CHOICES, settings.text_position),
        "dwell_s": settings.dwell_s,
        "reminder": _closest(REMINDER_CHOICES, settings.reminder_s),
        "release": _closest(RELEASE_CHOICES, settings.release_s),
        **{name: getattr(settings, name) for name in ZONE_SLIDERS},
        "pause_when_locked": settings.pause_when_locked,
        "pause_for_calls": settings.pause_for_calls,
        "start_with_windows": settings.start_with_windows,
        "camera_index": settings.camera_index,
    }


def settings_from_form(values: dict, base: Settings) -> Settings:
    return clamp(replace(
        base,
        chime=bool(values["chime"]),
        sound=SOUND_CHOICES[values["sound"]],
        volume=round(float(values["volume"])),
        notification=bool(values["notification"]),
        screen_border=bool(values["screen_border"]),
        border_color=values["border_color"],
        border_width=round(float(values["border_width"])),
        screen_text=bool(values["screen_text"]),
        custom_text=values["custom_text"],
        text_size=round(float(values["text_size"])),
        text_color=values["text_color"],
        text_background=bool(values["text_background"]),
        text_background_color=values["text_background_color"],
        text_padding_x=round(float(values["text_padding_x"])),
        text_padding_y=round(float(values["text_padding_y"])),
        text_position=TEXT_POSITION_CHOICES[values["text_position"]],
        screen_blur=bool(values["screen_blur"]),
        blur_level=round(float(values["blur_level"])),
        dwell_s=round(float(values["dwell_s"]), 2),
        reminder_s=REMINDER_CHOICES[values["reminder"]],
        release_s=RELEASE_CHOICES[values["release"]],
        **{name: round(float(values[name]), 2) for name in ZONE_SLIDERS},
        pause_when_locked=bool(values["pause_when_locked"]),
        pause_for_calls=bool(values["pause_for_calls"]),
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
        self._form_call_pause = base.pause_for_calls
        self._startup_requested = base.start_with_windows
        self._startup_state = base.start_with_windows

    @property
    def starts_with_windows(self) -> bool:
        return self._startup_state

    def update(self, values: dict) -> Settings:
        new = settings_from_form(values, self._last)
        if new.pause_for_calls == self._form_call_pause and self._path.is_file():
            new = replace(new, pause_for_calls=load_settings(self._path).pause_for_calls)
        self._form_call_pause = bool(values["pause_for_calls"])
        if new.start_with_windows != self._startup_requested:  # only touch the registry when the box changes
            self._startup_requested = new.start_with_windows
            self._startup_state = (self._set_startup(new.start_with_windows) if self._set_startup
                                   else new.start_with_windows)
        new = replace(new, start_with_windows=self._startup_state)
        if new != self._last:
            self._save(self._path, new)
            self._last = new
        return new


class SettingsPreview:
    """Show current screen-effect controls immediately, independently of detection."""

    def __init__(self, overlay: Border):
        self._overlay = overlay

    def update(self, values: dict, active: bool) -> None:
        if not active:
            self.close()
            return
        defaults = Settings()
        form = form_values(defaults) | {name: values[name] for name in EFFECT_FIELDS}
        self._overlay.update(settings_from_form(form, defaults), True)

    def close(self) -> None:
        self._overlay.close()


def run_settings_window(path: Path | None = None) -> int:
    import tkinter as tk
    from tkinter import colorchooser, ttk

    path = path or settings_path()
    base = load_settings(path)
    values = form_values(base)

    root = tk.Tk()
    root.title("Hands Down settings")
    root.resizable(False, False)
    outer = ttk.Frame(root, padding=16)
    outer.grid(sticky="nsew")
    tabs = ttk.Notebook(outer)
    tabs.grid(row=0, column=0, columnspan=3, sticky="nsew")
    frame = ttk.Frame(tabs, padding=12)
    tabs.add(frame, text="Alerts")

    chime = tk.BooleanVar(value=values["chime"])
    sound = tk.StringVar(value=values["sound"])
    volume = tk.DoubleVar(value=values["volume"])
    release = tk.StringVar(value=values["release"])
    pause_for_calls = tk.BooleanVar(value=values["pause_for_calls"])
    pause_when_locked = tk.BooleanVar(value=values["pause_when_locked"])
    notification = tk.BooleanVar(value=values["notification"])
    screen_border = tk.BooleanVar(value=values["screen_border"])
    screen = {name: (tk.BooleanVar if name in ("screen_text", "screen_blur", "text_background") else
                     tk.DoubleVar if name in ("border_width", "blur_level", "text_size", "text_padding_x", "text_padding_y") else tk.StringVar)(value=values[name])
              for name in SCREEN_FIELDS}
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

    def test_sound() -> None:
        try:
            play_chime(SOUND_CHOICES[sound.get()], round(volume.get()))
        except Exception:
            pass  # a missing audio device should not close the settings window

    ttk.Button(frame, text="Play", command=test_sound).grid(row=row - 1, column=2, sticky="w")

    def slider(label: str, variable: tk.DoubleVar, low: float, high: float, fmt: str) -> None:
        shown = ttk.Label(frame, text=fmt.format(variable.get()))
        add(label, ttk.Scale(frame, from_=low, to=high, variable=variable, length=180,
                             command=lambda _value: shown.config(text=fmt.format(variable.get()))))
        shown.grid(row=row - 1, column=2, sticky="w")

    slider("Volume", volume, *LIMITS["volume"], "{:.0f}%")
    hint("63% is as loud as the old Normal")
    add("Notification", ttk.Checkbutton(frame, variable=notification))
    frame = ttk.Frame(tabs, padding=12)
    tabs.add(frame, text="Screen effects")
    screen_tab = frame
    frame = ttk.LabelFrame(screen_tab, text="Border and blur", padding=12)
    frame.grid(row=0, column=0, sticky="nw", padx=(0, 12))
    row = 0
    add("Screen border", ttk.Checkbutton(frame, variable=screen_border))

    def color_control(label: str, name: str) -> None:
        def choose() -> None:
            _, chosen = colorchooser.askcolor(color=screen[name].get(), parent=root, title=label)
            if chosen:
                screen[name].set(chosen)
        add(label, ttk.Button(frame, textvariable=screen[name], command=choose))

    color_control("Border color", "border_color")
    slider("Border thickness", screen["border_width"], *LIMITS["border_width"], "{:.0f}")
    add("Blur screen", ttk.Checkbutton(frame, variable=screen["screen_blur"]))
    slider("Blur strength", screen["blur_level"], *LIMITS["blur_level"], "{:.0f}")
    hint("Blurred snapshot until your hand moves away")
    if sys.platform == "darwin":
        hint("Blur needs Screen Recording permission")

    frame = ttk.LabelFrame(screen_tab, text="Reminder text", padding=12)
    frame.grid(row=0, column=1, sticky="nw")
    row = 0
    add("Show text", ttk.Checkbutton(frame, variable=screen["screen_text"]))
    add("Message", ttk.Entry(frame, textvariable=screen["custom_text"], width=26))
    slider("Text size", screen["text_size"], *LIMITS["text_size"], "{:.0f}")
    color_control("Text color", "text_color")
    add("Location", ttk.Combobox(frame, textvariable=screen["text_position"], state="readonly",
                                values=list(TEXT_POSITION_CHOICES), width=18))
    add("Show background", ttk.Checkbutton(frame, variable=screen["text_background"]))
    color_control("Background color", "text_background_color")
    slider("Horizontal padding", screen["text_padding_x"], *LIMITS["text_padding_x"], "{:.0f}")
    slider("Vertical padding", screen["text_padding_y"], *LIMITS["text_padding_y"], "{:.0f}")
    hint("Padding changes the background size")
    ttk.Label(screen_tab, text="Live desktop preview while this tab is open. Effects may appear in screen sharing.",
              foreground="grey").grid(row=1, column=0, columnspan=2, sticky="w", pady=(12, 0))

    frame = ttk.Frame(tabs, padding=12)
    tabs.add(frame, text="Detection")
    row = 0

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
    add("Pause for calls", ttk.Checkbutton(frame, variable=pause_for_calls))
    hint("Automatically release the camera while another app uses it; resume when free")
    hint("Uses OS camera activity; camera-off calls do not trigger a pause")
    add("Pause while the screen is locked", ttk.Checkbutton(frame, variable=pause_when_locked))
    if startup.startup_label():
        add(startup.startup_label(), ttk.Checkbutton(frame, variable=start))
    add("Camera number", ttk.Spinbox(frame, from_=0, to=9, textvariable=camera, width=5))

    saver = AutoSaver(path, base, set_startup=startup.set_start_at_login if startup.startup_label() else None)
    pending = [None]
    preview = SettingsPreview(Border(border_command(), preview=True))
    preview_pending = [None]

    def update_preview() -> None:
        preview_pending[0] = None
        active = tabs.select() == str(screen_tab)
        root.attributes("-topmost", active)  # keep the controls visible above the preview
        try:
            preview.update({"screen_border": screen_border.get(),
                            **{name: variable.get() for name, variable in screen.items()}}, active)
        except (tk.TclError, ValueError, KeyError, OSError):
            preview.close()

    def schedule_preview(*_args) -> None:
        if preview_pending[0] is not None:
            root.after_cancel(preview_pending[0])
        preview_pending[0] = root.after(40, update_preview)

    tabs.bind("<<NotebookTabChanged>>", lambda _event: update_preview())
    for variable in (screen_border, *screen.values()):
        variable.trace_add("write", schedule_preview)

    def save_now() -> None:
        pending[0] = None
        try:
            saver.update({
                "chime": chime.get(), "sound": sound.get(), "volume": volume.get(),
                "notification": notification.get(), "screen_border": screen_border.get(), "dwell_s": dwell.get(),
                **{name: variable.get() for name, variable in screen.items()},
                "reminder": reminder.get(),
                "pause_for_calls": pause_for_calls.get(),
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
                     start, camera, pause_for_calls, *zone.values(), *screen.values()):
        variable.trace_add("write", changed)

    def close() -> None:
        if preview_pending[0] is not None:
            root.after_cancel(preview_pending[0])
        preview.close()
        if pending[0] is not None:
            root.after_cancel(pending[0])
            save_now()
        root.destroy()

    def refresh_call_preference() -> None:
        # The tray can change this same preference while Settings is open.
        if pending[0] is None:
            current = load_settings(path).pause_for_calls
            if pause_for_calls.get() != current:
                pause_for_calls.set(current)
        root.after(500, refresh_call_preference)

    root.after(500, refresh_call_preference)

    hint_row = 1
    ttk.Label(outer, text="Changes are saved as you make them", foreground="grey").grid(
        row=hint_row, column=0, columnspan=2, sticky="w", pady=(12, 0))
    ttk.Button(outer, text="Close", command=close).grid(row=hint_row, column=2, sticky="e", pady=(12, 0))
    root.protocol("WM_DELETE_WINDOW", close)
    try:
        root.mainloop()
    finally:
        preview.close()
    return 0
