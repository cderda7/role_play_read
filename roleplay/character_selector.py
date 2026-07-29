"""
Picks which character the student plays in a given scene: whoever has the
most "plot points". This is a computable, checkable heuristic rather than a
vibe -- given the same chapter text, it always returns the same answer, and
it's exactly the kind of thing worth testing against known-good cases
(Act I, Scene I should pick Benvolio, who's present through the whole brawl
and the entire Romeo/Rosaline exchange after it; Act IV, Scene V should pick
the Nurse, who discovers Juliet and carries the scene's grief, not Peter,
whose comic musician banter is clustered at the very end).

Neither raw word count nor raw turn count alone gets both cases right:

  - Word count lets one long, dense monologue outweigh a character who's
    actually in more of the scene's back-and-forth (Act I Scene I: Romeo's
    502 words beats Benvolio's 383, even though Benvolio is the one present
    across the whole brawl and the Rosaline exchange after it).
  - Turn count alone fixes that (Benvolio 24 turns vs Romeo 16), but it can
    be fooled by a character with many short turns clustered in one small
    part of the scene -- in Act IV Scene V, Peter's comic musician exchange
    at the very end gives him more raw turns (10) than the Nurse (7), despite
    the Nurse carrying the scene's actual emotional/plot weight.

The metric used here is turns x breadth: number of speaking turns, weighted
by how much of the scene the character is actually spread across. Breadth is
measured by splitting the chapter into 4 equal positional quartiles (by
character offset in the text) and counting how many distinct quartiles the
character has at least one turn in. A character clustered in a single
quartile -- however many turns they rack up there -- is weighted down
relative to one who's present throughout. This is what "most plot points"
is actually trying to capture: not just how much someone talks, but how much
of the scene's own arc they're present for."""

from __future__ import annotations

import re
from collections import Counter
from typing import Dict, List

# A line that's its own paragraph, entirely capital letters (allowing
# apostrophes and spaces for names like "LADY CAPULET" or "CAPULET'S
# COUSIN"), ending in a period -- the speech-prefix convention this edition
# uses throughout.
SPEECH_LABEL_RE = re.compile(r"^([A-Z][A-Z’' ]+)\.\s*$", re.MULTILINE)

# Crowd/unnamed roles -- excluded because they're not characters a student
# would meaningfully role-play as for literary analysis (no individual
# motivation or arc to reason about), not because they don't speak. Matched
# after stripping trailing whitespace; ordinal crowd roles ("FIRST
# SERVANT") are excluded by pattern rather than being listed one by one.
EXCLUDED_LABELS = {"SERVANT", "CHORUS", "THE PROLOGUE", "PAGE"}
EXCLUDED_PREFIX_RE = re.compile(r"^(FIRST|SECOND|THIRD)\s")


def _is_excluded(label: str) -> bool:
    return label in EXCLUDED_LABELS or bool(EXCLUDED_PREFIX_RE.match(label))


def word_counts_by_character(chapter_text: str) -> Dict[str, int]:
    """Returns {character_label: total words spoken} for every eligible
    (non-crowd) speaking character in this chapter's text."""
    labels = list(SPEECH_LABEL_RE.finditer(chapter_text))
    counts: Counter[str] = Counter()

    for i, match in enumerate(labels):
        label = match.group(1).strip()
        if _is_excluded(label):
            continue
        speech_start = match.end()
        speech_end = labels[i + 1].start() if i + 1 < len(labels) else len(chapter_text)
        speech = chapter_text[speech_start:speech_end]
        counts[label] += len(speech.split())

    return dict(counts)


def turn_counts_by_character(chapter_text: str) -> Dict[str, int]:
    """Returns {character_label: number of speaking turns} for every
    eligible (non-crowd) speaking character in this chapter's text.

    Turn count is closer than word count to what "most plot points" means
    for a role-play checkpoint script: a character who's present across more
    distinct beats of the scene gives the branching script more places to
    actually put a decision. But raw turn count alone can still be misled by
    turns clustered in one narrow part of the scene -- see
    character_significance() and the module docstring for the Act IV Scene V
    case this doesn't handle on its own."""
    labels = [
        m.group(1).strip() for m in SPEECH_LABEL_RE.finditer(chapter_text) if not _is_excluded(m.group(1).strip())
    ]
    return dict(Counter(labels))


QUARTILES = 4


def _quartile_breadth_by_character(chapter_text: str) -> Dict[str, int]:
    """Returns {character_label: number of distinct positional quartiles the
    character has at least one turn in}, splitting the chapter into QUARTILES
    equal segments by character offset. A character who speaks in all 4
    quartiles is present throughout the scene; a character confined to 1
    quartile is only present for a narrow slice of it, no matter how many
    turns they get within that slice."""
    labels = list(SPEECH_LABEL_RE.finditer(chapter_text))
    text_length = len(chapter_text)
    quartile_presence: Dict[str, set] = {}

    for match in labels:
        label = match.group(1).strip()
        if _is_excluded(label):
            continue
        quartile = min(int(match.start() / text_length * QUARTILES), QUARTILES - 1) if text_length else 0
        quartile_presence.setdefault(label, set()).add(quartile)

    return {label: len(quartiles) for label, quartiles in quartile_presence.items()}


def character_significance(chapter_text: str) -> Dict[str, int]:
    """Returns {character_label: significance score} = turns x quartile
    breadth, for every eligible speaking character in this chapter's text.
    This is the metric select_character() ranks by -- see the module
    docstring for why neither turns nor breadth alone is enough.

    Validated against two cases: Act I Scene I picks BENVOLIO (score 72 =
    24 turns x 3 quartiles) over Sampson (40) and Romeo (32); Act IV Scene V
    picks the NURSE (score 21 = 7 turns x 3 quartiles) over Peter (20 = 10
    turns x 2 quartiles), whose comic musician exchange is clustered at the
    scene's end."""
    turns = turn_counts_by_character(chapter_text)
    breadth = _quartile_breadth_by_character(chapter_text)
    return {label: count * breadth.get(label, 1) for label, count in turns.items()}


def select_character(chapter_text: str) -> str:
    """The character with the highest turns x quartile-breadth significance
    score in this chapter -- see character_significance(). Raises if no
    eligible speaking character is found -- better to fail loudly during
    content authoring than to silently hand back a nonsense default."""
    scores = character_significance(chapter_text)
    if not scores:
        raise ValueError("No eligible speaking character found in this chapter's text.")
    return max(scores, key=scores.get)


def select_characters_for_all_chapters(chapters: List[dict]) -> Dict[str, str]:
    """Convenience for content authoring: {chapter_id: selected_character}
    across a whole chapters.json-shaped list, so the choice for every scene
    can be reviewed at once rather than one at a time."""
    return {ch["chapter_id"]: select_character(ch["text"]) for ch in chapters}
