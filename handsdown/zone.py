"""Stage 1 detection: is a hand in the zone around her head?

Coordinates are normalised to the frame. The zone is built from the face's bounding box:
it covers hair above, beside and below the face, with the mouth and chin cut out.
"""

from dataclasses import dataclass

from handsdown.landmarks import Box, Observation

ABOVE = 0.7  # default face heights above the face box (the face mesh stops at the forehead)
BELOW = 0.8  # default face heights below it, for hair that hangs past the jaw
MIN_POINTS = 3  # hand landmarks that must be inside the zone to count as contact


@dataclass(frozen=True)
class Zone:
    outer: Box
    excluded: Box | None  # mouth and chin: hands here are usually resting or holding a cup

    def contains(self, x: float, y: float) -> bool:
        return _inside(self.outer, x, y) and not (self.excluded is not None and _inside(self.excluded, x, y))


def _inside(box: Box, x: float, y: float) -> bool:
    x0, y0, x1, y1 = box
    return x0 <= x <= x1 and y0 <= y <= y1


def head_zone(face: Box, margin: float, above: float = ABOVE, below: float = BELOW, cutout: float = 1.0) -> Zone:
    """margin: face widths to each side; above, below: face heights; cutout scales the chin box (0 is off)."""
    x0, y0, x1, y1 = face
    w, h = x1 - x0, y1 - y0
    outer = (x0 - margin * w, y0 - above * h, x1 + margin * w, y1 + below * h)
    if cutout <= 0:
        return Zone(outer, None)
    cx, cy = (x0 + x1) / 2, y0 + 0.95 * h  # centre of the mouth and chin box
    half_w, half_h = 0.3 * w * cutout, 0.4 * h * cutout
    return Zone(outer, (cx - half_w, cy - half_h, cx + half_w, cy + half_h))


def hand_in_zone(hand, zone: Zone) -> bool:
    return sum(zone.contains(x, y) for x, y in hand) >= MIN_POINTS


def contact(observation: Observation, margin: float, above: float = ABOVE, below: float = BELOW,
            cutout: float = 1.0) -> bool:
    if observation.face_box is None:
        return False
    zone = head_zone(observation.face_box, margin, above, below, cutout)
    return any(hand_in_zone(hand, zone) for hand in observation.hands)
