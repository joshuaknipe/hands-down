"""The tray icon (a thin ring whose colour shows the state) and its menu. Discreet if her screen is shared."""

from dataclasses import dataclass

from PIL import Image, ImageDraw

STATE_COLOURS = {
    None: (150, 150, 150),  # starting
    "watching": (88, 166, 160),
    "not_tracking": (214, 176, 92),
    "camera_busy": (205, 110, 92),
    "paused": (150, 150, 150),
}

STATE_LABELS = {
    None: "Starting",
    "watching": "Watching",
    "not_tracking": "Can't see you",
    "camera_busy": "Camera in use by another app",
    "paused": "Paused",
}


def draw_icon(state: str | None, size: int = 64) -> Image.Image:
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    pad = size // 8
    colour = STATE_COLOURS.get(state, STATE_COLOURS[None])
    ImageDraw.Draw(image).ellipse((pad, pad, size - 1 - pad, size - 1 - pad), outline=colour + (255,),
                                  width=max(2, size // 9))
    return image


@dataclass(frozen=True)
class MenuItem:
    label: str
    action: str | None
    enabled: bool = True


def menu_items(state: str | None, paused: bool, camera_open: bool = False) -> list[MenuItem]:
    items = [MenuItem(STATE_LABELS.get(state, STATE_LABELS[None]), None, enabled=False)]
    if paused:
        items.append(MenuItem("Resume", "resume"))
    else:
        items += [
            MenuItem("Pause for call", "pause_call"),
            MenuItem("Pause 15 minutes", "pause_15"),
            MenuItem("Pause 1 hour", "pause_60"),
        ]
    items += [
        MenuItem("That wasn't me", "false_alert"),
        MenuItem("Hide camera", "hide_camera") if camera_open else MenuItem("Show camera", "show_camera"),
        MenuItem("Summary", "summary"),
        MenuItem("Settings…", "settings"),
        MenuItem("Open log folder", "open_log"),
        MenuItem("Quit", "quit"),
    ]
    return items


# macOS only shows menu bar icons that fit to the right of a MacBook's notch, and puts a new app's
# icon furthest left, so on a crowded bar it is hidden. Ask for a spot near the clock instead.
MENU_BAR_POSITION_KEY = "NSStatusItem Preferred Position Item-0"
MENU_BAR_POSITION = 300.0


def place_menu_bar_icon(defaults=None) -> None:
    """Set the icon's position on first run only, so a position the user drags it to is kept."""
    if defaults is None:
        from Foundation import NSUserDefaults

        defaults = NSUserDefaults.standardUserDefaults()
    if defaults.objectForKey_(MENU_BAR_POSITION_KEY) is None:
        defaults.setFloat_forKey_(MENU_BAR_POSITION, MENU_BAR_POSITION_KEY)
