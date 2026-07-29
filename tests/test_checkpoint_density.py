import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from roleplay.checkpoint_density import checkpoint_density


def _load_chapters():
    path = os.path.join(os.path.dirname(__file__), "..", "data", "chapters.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def test_act1_scene1_is_complex():
    # 2088 words -- well above the 1400 threshold.
    text = next(c for c in _load_chapters() if c["chapter_id"] == "act1_scene1")["text"]
    density = checkpoint_density(text)
    assert density.is_complex is True
    assert density.major == 2
    assert density.minor_min == 5


def test_act5_scene2_is_standard():
    # 247 words -- well below the threshold.
    text = next(c for c in _load_chapters() if c["chapter_id"] == "act5_scene2")["text"]
    density = checkpoint_density(text)
    assert density.is_complex is False
    assert density.major == 1
    assert density.minor_min == 3


def test_distribution_is_reasonably_balanced():
    """Not a strict assertion about the threshold value itself -- just a
    guard against the split becoming wildly lopsided (e.g. every scene
    complex, or every scene standard) if the source text changes."""
    chapters = _load_chapters()
    complex_count = sum(1 for c in chapters if checkpoint_density(c["text"]).is_complex)
    assert 5 <= complex_count <= len(chapters) - 5
