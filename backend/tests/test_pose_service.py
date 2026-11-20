from __future__ import annotations

import numpy as np

from app.services.pose_service import render_pose_skeleton, view_key


def test_view_key_normalises_labels():
    assert view_key("side profile") == "side"
    assert view_key("three-quarter view") == "three_quarter"
    assert view_key("back view") == "back"
    assert view_key("front") == "front"
    assert view_key("front-no-backpack-20261111-v2") == "front"
    assert view_key("") == "front"


def test_skeleton_is_drawn_at_the_requested_size():
    image = render_pose_skeleton("front", 256, 384)
    assert image.size == (256, 384)
    array = np.asarray(image)
    assert (array > 20).mean() > 0.01


def test_side_and_front_skeletons_differ():
    front = np.asarray(render_pose_skeleton("front", 256, 384))
    side = np.asarray(render_pose_skeleton("side", 256, 384))
    assert not np.array_equal(front, side)


def test_back_skeleton_omits_face_points():
    back = np.asarray(render_pose_skeleton("back", 256, 384))
    front = np.asarray(render_pose_skeleton("front", 256, 384))
    assert not np.array_equal(front, back)
