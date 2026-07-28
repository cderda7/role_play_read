"""
Regression coverage for chunk_play.py, added after two real bugs were caught
by eyeballing printed output rather than by any test: (1) the table of
contents colliding with real scene headings and duplicating a chapter with
wrong content, and (2) the Prologue/Chorus text being silently dropped
instead of prepended as the module docstring claimed. Both are asserted
here so they can't silently come back.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from chunk_play import chunk


def _load_raw() -> str:
    path = os.path.join(os.path.dirname(__file__), "..", "data", "romeoandjuliet.txt")
    with open(path, encoding="utf-8") as f:
        return f.read()


def test_exactly_24_chapters_no_duplicates():
    chapters = chunk(_load_raw())
    ids = [c["chapter_id"] for c in chapters]
    assert len(ids) == 24
    assert len(set(ids)) == 24, f"duplicate chapter_id(s): {[i for i in ids if ids.count(i) > 1]}"


def test_no_front_matter_leaked_into_a_chapter():
    """The table of contents and Dramatis Personae list aren't spoken
    content -- if either shows up inside a chapter's text, the front-matter
    slicing in load_body() broke again."""
    chapters = chunk(_load_raw())
    for c in chapters:
        assert "Dramatis Person" not in c["text"], c["chapter_id"]
        assert "MERCUTIO, kinsman to the Prince" not in c["text"], c["chapter_id"]  # a Dramatis Personae line


def test_prologue_is_prepended_to_act1_scene1():
    chapters = chunk(_load_raw())
    act1_scene1 = next(c for c in chapters if c["chapter_id"] == "act1_scene1")
    assert "Two households, both alike in dignity" in act1_scene1["text"]
    # and it comes first -- prepended, not appended after the real scene
    assert act1_scene1["text"].index("Two households") < act1_scene1["text"].index("Enter Sampson and Gregory")


def test_act2_chorus_is_prepended_to_act2_scene1():
    chapters = chunk(_load_raw())
    act2_scene1 = next(c for c in chapters if c["chapter_id"] == "act2_scene1")
    assert "Now old desire doth in his deathbed lie" in act2_scene1["text"]


def test_act1_scene1_ends_where_scene_ends_not_bleeding_into_scene_2():
    chapters = chunk(_load_raw())
    act1_scene1 = next(c for c in chapters if c["chapter_id"] == "act1_scene1")
    assert "I’ll pay that doctrine, or else die in debt" in act1_scene1["text"]
    assert "Enter Capulet, Paris and Servant" not in act1_scene1["text"]  # that's Scene II
