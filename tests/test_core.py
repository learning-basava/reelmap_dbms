"""Tests for the parts that don't need a database: drawing, text filling and the PDF."""
import stickfigure as sf
from generator import clip, fill
from pdf_export import build_pdf, latin1


def test_every_pose_shot_and_prop_draws():
    for pose in sf.POSES:
        for shot in sf.SHOTS:
            for prop in sf.PROPS:
                shapes = sf.frame_shapes(pose, shot, prop)
                assert shapes, (pose, shot, prop)
                svg = sf.to_svg(pose, shot, prop)
                assert svg.startswith("<svg") and svg.endswith("</svg>")


def test_unknown_pose_falls_back_to_standing():
    assert sf.frame_shapes("dance", "medium") == sf.frame_shapes("stand", "medium")


def test_fill_replaces_known_placeholders_only():
    ctx = {"topic": "home workout", "Topic": "Home workout", "audience": "students"}
    assert fill("3 {topic} tips for {audience}", ctx) == "3 home workout tips for students"
    assert fill("{Topic} in 30 seconds", ctx) == "Home workout in 30 seconds"
    assert fill("Keep {unknown} as is", ctx) == "Keep {unknown} as is"


def test_clip_respects_column_limits():
    assert len(clip("x" * 500, "on_screen_text")) == 80
    assert clip("  short   text ", "title") == "short text"


def test_latin1_replaces_smart_characters():
    assert latin1("It’s “great” – ₹99") == "It's \"great\" - Rs. 99"


def test_pdf_builds():
    project = {"topic": "home workout", "niche": "Fitness", "format_name": "How-To Tutorial",
               "platform": "Instagram Reels", "target_audience": "students"}
    idea = {"title": "Test idea", "hook": "A hook", "description": "A description."}
    frames = [{"frame_no": i, "shot_type": shot, "pose": "talk", "prop": "sparkle", "action_text": "Do this.",
               "dialogue": "Say that.", "on_screen_text": "Text", "duration_sec": 5}
              for i, shot in enumerate(["wide", "medium", "close_up"] * 3, start=1)]
    pdf = build_pdf(project, idea, frames)
    assert pdf.startswith(b"%PDF") and len(pdf) > 5000
