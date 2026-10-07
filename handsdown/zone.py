"""Stage 1 detection: is a hand in the zone around her head?

Coordinates are normalised to the frame. The zone is built from the face's bounding box:
it covers hair above, beside and below the face, with the mouth and chin cut out.
"""

from dataclasses import dataclass

from handsdown.landmarks import Box, Observation

ABOVE = 0.7  # face heights above the face box (the face mesh stops at the forehead)
BELOW = 0.8  # face heights below it, for hair that hangs past the jaw
MIN_POINTS = 3  # hand landmarks that must be inside the zone to count as contact


@dataclass(frozen=True)
class Zone:
    outer: Box
    excluded: Box  # mouth and chin: hands here are usually resting or holding a cup

    def contains(self, x: float, y: float) -> bool:
        return _inside(self.outer, x, y) and not _inside(self.excluded, x, y)


def _inside(box: Box, x: float, y: float) -> bool:
    x0, y0, x1, y1 = box
    return x0 <= x <= x1 and y0 <= y <= y1


def head_zone(face: Box, margin: float) -> Zone:
    x0, y0, x1, y1 = face
    w, h = x1 - x0, y1 - y0
    outer = (x0 - margin * w, y0 - ABOVE * h, x1 + margin * w, y1 + BELOW * h)
    excluded = (x0 + 0.2 * w, y0 + 0.55 * h, x1 - 0.2 * w, y1 + 0.35 * h)
    return Zone(outer, excluded)


def hand_in_zone(hand, zone: Zone) -> bool:
    return sum(zone.contains(x, y) for x, y in hand) >= MIN_POINTS


def contact(observation: Observation, margin: float) -> bool:
    if observation.face_box is None:
        return False
    zone = head_zone(observation.face_box, margin)
    return any(hand_in_zone(hand, zone) for hand in observation.hands)
