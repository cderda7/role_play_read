"""
Regression coverage for character_selector.py. Two known cases are worth
pinning down, because neither raw word count nor raw turn count alone gets
both of them right (see the module docstring for the full reasoning):

  - Act I, Scene I: Benvolio should beat Romeo, even though Romeo has more
    total words (one long monologue vs. Benvolio's sustained back-and-forth
    across the scene).
  - Act IV, Scene V: the Nurse should beat Peter, even though Peter has more
    raw turns (a comic musician exchange clustered at the very end of the
    scene) -- this is the case that motivated weighting turns by how much of
    the scene the character is actually spread across (quartile breadth),
    not just counting them.
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from roleplay.character_selector import (
    character_significance,
    select_character,
    turn_counts_by_character,
    word_counts_by_character,
)


def _load_chapters():
    path = os.path.join(os.path.dirname(__file__), "..", "data", "chapters.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _chapter(chapter_id):
    return next(c for c in _load_chapters() if c["chapter_id"] == chapter_id)


def test_act1_scene1_picks_benvolio_by_significance():
    text = _chapter("act1_scene1")["text"]
    assert select_character(text) == "BENVOLIO"


def test_act1_scene1_word_count_would_have_picked_romeo():
    """Documents WHY word count alone isn't the metric -- if this ever stops
    being true (e.g. the source text changes), the module docstring's
    reasoning needs re-checking too."""
    text = _chapter("act1_scene1")["text"]
    words = word_counts_by_character(text)
    assert max(words, key=words.get) == "ROMEO"
    scores = character_significance(text)
    assert max(scores, key=scores.get) == "BENVOLIO"


def test_act4_scene5_picks_nurse_not_peter():
    """Documents WHY turn count alone isn't the metric either: Peter's
    clustered end-of-scene banter gives him more raw turns than the Nurse,
    but the quartile-breadth weighting fixes it."""
    text = _chapter("act4_scene5")["text"]
    turns = turn_counts_by_character(text)
    assert max(turns, key=turns.get) == "PETER"
    assert select_character(text) == "NURSE"


def test_crowd_roles_are_never_selected():
    crowd_roles = {"SERVANT", "FIRST SERVANT", "SECOND SERVANT", "FIRST CITIZEN", "FIRST MUSICIAN", "CHORUS"}
    for ch in _load_chapters():
        picked = select_character(ch["text"])
        assert picked not in crowd_roles, f"{ch['chapter_id']} picked a crowd role: {picked}"


def test_every_chapter_has_a_selectable_character():
    for ch in _load_chapters():
        picked = select_character(ch["text"])
        assert picked, ch["chapter_id"]
