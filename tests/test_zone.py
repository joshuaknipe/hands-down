import pytest

from handsdown.landmarks import Observation
from handsdown.zone import contact, hand_in_zone, head_zone

FACE = (0.4, 0.3, 0.6, 0.6)  # 0.2 wide, 0.3 tall


def hand_at(x, y, n=21):
    return tuple((x, y) for _ in range(n))


def test_zone_reaches_above_beside_and_below_the_face():
    zone = head_zone(FACE, margin=0.5)
    assert zone.outer == pytest.approx((0.3, 0.09, 0.7, 0.84))


def test_mouth_and_chin_are_cut_out():
    zone = head_zone(FACE, margin=0.5)
    assert zone.excluded == pytest.approx((0.44, 0.465, 0.56, 0.705))
    assert not zone.contains(0.5, 0.55)  # chin
    assert zone.contains(0.5, 0.2)  # scalp above the face
    assert zone.contains(0.33, 0.45)  # beside the face
    assert zone.contains(0.38, 0.8)  # long hair below the jaw, to the side


@pytest.mark.parametrize("x, y, expected", [
    (0.33, 0.4, True),  # temple
    (0.5, 0.15, True),  # top of the head
    (0.5, 0.6, False),  # chin rest
    (0.9, 0.5, False),  # far away
])
def test_hand_in_zone(x, y, expected):
    assert hand_in_zone(hand_at(x, y), head_zone(FACE, 0.5)) is expected


def test_a_couple_of_fingertips_on_the_edge_are_not_contact():
    hand = hand_at(0.33, 0.4, n=2) + hand_at(0.9, 0.5, n=19)
    assert not hand_in_zone(hand, head_zone(FACE, 0.5))


def test_contact_needs_a_face_and_a_hand_in_the_zone():
    temple = (hand_at(0.33, 0.4),)
    assert contact(Observation(0, temple, True, FACE), 0.5)
    assert not contact(Observation(0, temple, False, None), 0.5)
    assert not contact(Observation(0, (), True, FACE), 0.5)
    assert contact(Observation(0, (hand_at(0.9, 0.5),) + temple, True, FACE), 0.5)  # either hand counts


def test_wider_margin_reaches_further():
    hand = hand_at(0.27, 0.4)
    assert not hand_in_zone(hand, head_zone(FACE, 0.5))
    assert hand_in_zone(hand, head_zone(FACE, 0.8))
