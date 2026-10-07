"""Hands Down: the tray app that ties the camera loop, alerts, settings and log together."""

import os
import subprocess
import sys
import threading

import pystray

from handsdown.alerts import Alerter, mac_notify, play_chime
from handsdown.camera import open_first_camera
from handsdown.engine import Engine
from handsdown.eventlog import EventLog
from handsdown.paths import log_dir, settings_path
from handsdown.settings import SettingsStore
from handsdown.tray import STATE_LABELS, draw_icon, menu_items

PAUSES = {"pause_call": (None, "call"), "pause_15": (15 * 60, "15 min"), "pause_60": (60 * 60, "1 hour")}


def settings_command() -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, "--settings"]
    return [sys.executable, "-m", "handsdown", "--settings"]


def open_folder(folder) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        os.startfile(folder)
    else:
        subprocess.Popen(["open", str(folder)])


def run_app() -> int:
    log = EventLog(log_dir())
    store = SettingsStore(settings_path(), warn=lambda message: log.write("error", message=message))
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

    def act(action: str) -> None:
        if action in PAUSES:
            seconds, reason = PAUSES[action]
            engine.pause(seconds, reason)
        elif action == "resume":
            engine.resume()
        elif action == "false_alert":
            engine.mark_false_alert()
        elif action == "settings":
            subprocess.Popen(settings_command())
        elif action == "open_log":
            open_folder(log_dir())
        elif action == "quit":
            engine.stop()
            icon.stop()
        icon.update_menu()

    def item(entry):
        return pystray.MenuItem(entry.label, lambda: act(entry.action), enabled=entry.enabled)

    icon.menu = pystray.Menu(lambda: (item(entry) for entry in menu_items(engine.state, engine.paused)))

    def setup(tray_icon) -> None:
        tray_icon.visible = True
        threading.Thread(target=engine.run, name="engine", daemon=True).start()

    icon.run(setup=setup)
    return 0
