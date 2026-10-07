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


def menu_items(state: str | None, paused: bool) -> list[MenuItem]:
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
        MenuItem("Settings…", "settings"),
        MenuItem("Open log folder", "open_log"),
        MenuItem("Quit", "quit"),
    ]
    return items
