"""Hands Down: the tray app that ties the camera loop, alerts, settings and log together."""

import os
import subprocess
import sys
import threading

import pystray

from handsdown.alerts import Alerter, mac_notify, play_chime
from handsdown.camera import open_first_camera
from handsdown.commands import camera_view_command, settings_command, summary_command
from handsdown.engine import Engine
from handsdown.eventlog import EventLog
from handsdown.paths import log_dir, settings_path
from handsdown.preview import CameraView, annotate, encode
from handsdown.settings import SettingsStore
from handsdown.single import acquire
from handsdown.tray import STATE_LABELS, draw_icon, menu_items, place_menu_bar_icon

PAUSES = {"pause_call": (None, "call"), "pause_15": (15 * 60, "15 min"), "pause_60": (60 * 60, "1 hour")}


def open_folder(folder) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        os.startfile(folder)
    else:
        subprocess.Popen(["open", str(folder)])


def tell_already_running() -> None:
    """A second launch quits, but says why instead of silently doing nothing."""
    text = "Hands Down is already running. Its ring is in the system tray."
    try:
        if sys.platform == "win32":
            import ctypes

            ctypes.windll.user32.MessageBoxW(None, text, "Hands Down", 0x40)  # MB_ICONINFORMATION
        else:
            mac_notify("Hands Down", "Already running")
    except Exception:
        pass


def run_app() -> int:
    log = EventLog(log_dir())
    lock = acquire(settings_path().parent / "running.lock")
    if lock is None:
        log.write("error", message="Another copy is already running")
        tell_already_running()
        return 0
    store = SettingsStore(settings_path(), warn=lambda message: log.write("error", message=message))
    if sys.platform == "darwin":
        try:
            place_menu_bar_icon()
        except Exception as exc:  # cosmetic: never stop the app over it
            log.write("error", message=f"Could not place the menu bar icon: {exc}")
    icon = pystray.Icon("handsdown", draw_icon(None), "Hands Down")

    def notify(title: str, text: str) -> None:
        if sys.platform == "win32":
            icon.notify(text, title)
        else:
            mac_notify(title, text)

    def sound() -> None:
        settings = store.get()
        play_chime(settings.sound, settings.volume)

    alerter = Alerter(store.get, sound, notify, warn=lambda message: log.write("error", message=message))

    def on_state(state: str) -> None:
        icon.icon = draw_icon(state)
        icon.title = f"Hands Down - {STATE_LABELS[state]}"
        icon.update_menu()

    engine = Engine(store.get, log, alerter.alert, on_state, open_first_camera)
    view = CameraView(camera_view_command())

    def show(frame, observation, touching: bool, settings) -> None:
        if view.is_open:
            view.send(encode(annotate(frame, observation, settings, touching)))

    engine.frame_sink = show

    def act(action: str) -> None:
        if action in PAUSES:
            seconds, reason = PAUSES[action]
            engine.pause(seconds, reason)
        elif action == "resume":
            engine.resume()
        elif action == "false_alert":
            engine.mark_false_alert()
        elif action == "show_camera":
            view.open()
        elif action == "hide_camera":
            view.close()
        elif action == "summary":
            subprocess.Popen(summary_command())
        elif action == "settings":
            subprocess.Popen(settings_command())
        elif action == "open_log":
            open_folder(log_dir())
        elif action == "quit":
            view.close()
            engine.stop()
            icon.stop()
        icon.update_menu()

    def item(entry):
        return pystray.MenuItem(entry.label, lambda: act(entry.action), enabled=entry.enabled)

    icon.menu = pystray.Menu(lambda: (item(entry) for entry in menu_items(engine.state, engine.paused, view.is_open)))

    engine_thread = threading.Thread(target=engine.run, name="engine", daemon=True)

    def setup(tray_icon) -> None:
        tray_icon.visible = True
        engine_thread.start()

    icon.run(setup=setup)
    engine.stop()
    if engine_thread.is_alive():
        engine_thread.join(timeout=3)  # let it release the camera and log "stop"
    lock.release()
    return 0
