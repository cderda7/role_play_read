"""
Content-authoring script: turns the raw Gutenberg #1513 text into the
Chapter list the pipeline expects (roleplay.models.Chapter), one per
Act/Scene, and writes it to data/chapters.json.

Run once whenever the source text changes:
    python chunk_play.py

This is a one-time/occasional authoring step, not something the live
pipeline runs -- matches the same "static, precomputed, human-checked"
posture as everything else in this project.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

RAW_PATH = Path(__file__).parent / "data" / "romeoandjuliet.txt"
OUT_PATH = Path(__file__).parent / "data" / "chapters.json"

START_MARKER = "*** START OF THE PROJECT GUTENBERG EBOOK ROMEO AND JULIET ***"
END_MARKER = "*** END OF THE PROJECT GUTENBERG EBOOK ROMEO AND JULIET ***"

ACT_RE = re.compile(r"^ACT ([IVXLC]+)\s*$")
# Deliberately case-SENSITIVE, all-caps "SCENE" only. The table of contents
# at the top of the file lists scenes too, but in title case ("Scene I. A
# public place.") -- the real scene headings in the body are all-caps
# ("SCENE I. A public place."). Matching case-insensitively made the
# contents listing collide with the real headings and silently duplicated
# a chapter with the wrong content (caught by inspecting chapters.json
# after a first run -- see the note in the project history/commit for this
# file about why this is exact-case on purpose).
SCENE_RE = re.compile(r"^SCENE ([IVXLC]+)\.\s*(.*)$")

ROMAN_TO_INT = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7}


PROLOGUE_ANCHOR = "THE PROLOGUE"


def load_body(raw_text: str) -> str:
    """Returns just the play itself -- Prologue through the final scene.
    Deliberately starts at "THE PROLOGUE", not at the START marker: between
    those two points sits the table of contents and the Dramatis Personae
    list, neither of which is spoken content, and the table of contents in
    particular has its own "ACT I" / "Scene I." lines that would otherwise
    collide with the real parsing below.

    "THE PROLOGUE" appears TWICE in this file -- once as a contents-listing
    entry ("THE PROLOGUE.", with a trailing period, up near the top) and
    once as the real heading right before "Enter Chorus." and the actual
    sonnet. Using the first (plain .index()) grabbed the contents entry and
    silently pulled the whole table of contents into act1_scene1 -- caught
    by eyeballing the chunked output, not by a test, which is itself a
    reminder to add a real assertion for this rather than relying on
    reading the printed word counts. rindex() (last occurrence) is correct
    here specifically because this string is confirmed to appear exactly
    twice in the source file -- re-check that assumption if the source
    edition ever changes."""
    end = raw_text.index(END_MARKER)
    prologue_start = raw_text.rindex(PROLOGUE_ANCHOR)
    return raw_text[prologue_start:end]


def chunk(raw_text: str) -> list[dict]:
    """Returns a list of {chapter_id, order, act, scene, location, text}
    dicts, one per Act/Scene. The Prologue and any Act-opening Chorus speech
    are folded into the chapter that follows them -- they're short framing
    interludes, not scenes a teacher would assign a character role-play to
    on their own, and per the spoiler policy the Prologue's own text is the
    play's own "broadly known outcome" disclosure, not extra spoiler risk."""
    body = load_body(raw_text)
    lines = body.split("\n")

    chapters: list[dict] = []
    current_act: str | None = None
    current_scene: str | None = None
    current_location = ""
    buffer: list[str] = []
    # Text seen after an ACT heading (or before the very first one -- the
    # Prologue) but before the next SCENE heading: the Prologue itself and
    # Act II's opening Chorus speech both live here. Prepended to whichever
    # scene comes next rather than silently dropped -- an earlier version of
    # this script discarded it by accident; caught by checking chapters.json
    # for the Prologue's own text and not finding it there.
    preamble: list[str] = []

    def flush_scene():
        nonlocal buffer
        if current_act is not None and current_scene is not None and buffer:
            text = "\n".join(buffer).strip()
            if text:
                chapters.append(
                    {
                        "chapter_id": f"act{ROMAN_TO_INT[current_act]}_scene{ROMAN_TO_INT[current_scene]}",
                        "act": ROMAN_TO_INT[current_act],
                        "scene": ROMAN_TO_INT[current_scene],
                        "location": current_location,
                        "text": text,
                    }
                )
        buffer = []

    for line in lines:
        stripped = line.strip()
        act_match = ACT_RE.match(stripped)
        scene_match = SCENE_RE.match(stripped)

        if act_match:
            flush_scene()
            current_act = act_match.group(1)
            current_scene = None
            continue

        if scene_match:
            flush_scene()
            current_scene = scene_match.group(1)
            current_location = scene_match.group(2).strip()
            buffer = list(preamble)  # seed with the Prologue/Chorus text, if any
            preamble = []
            continue

        if current_scene is not None:
            buffer.append(line)
        else:
            preamble.append(line)

    flush_scene()  # last scene

    chapters.sort(key=lambda c: (c["act"], c["scene"]))
    for i, ch in enumerate(chapters):
        ch["order"] = i
    return chapters


def main() -> None:
    raw_text = RAW_PATH.read_text(encoding="utf-8")
    chapters = chunk(raw_text)

    OUT_PATH.write_text(json.dumps(chapters, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"{len(chapters)} chapters written to {OUT_PATH}")
    for ch in chapters:
        word_count = len(ch["text"].split())
        print(f"  [{ch['order']:2d}] {ch['chapter_id']:14s} ({word_count:4d} words) -- {ch['location']}")


if __name__ == "__main__":
    main()
