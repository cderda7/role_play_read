"""
Deterministic backstop alongside role B. Not a substitute for the LLM gate
-- a second, independent check that doesn't depend on model behavior at all,
for the plot points that matter most to catch. A question can be flagged by
this OR by role B; either one alone is enough to route it to human review.

SPOILER_KEYWORDS and CHAPTER_ORDER are placeholders, same spirit as
backend/syllabify.py's SYLLABLE_OVERRIDES in the immersive-reader project:
fill them in once the play is actually chunked into real chapters, rather
than guessing the shape before real content exists.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from .models import CandidateQuestion, KeywordFlag

# term (lowercase) -> chapter_id it first becomes fair game to mention.
# TODO: populate once chapters are chunked. Example shape once real:
#   "potion": "act4_scene1",
#   "friar laurence's letter": "act5_scene2",
#   "paris": "act5_scene3",
SPOILER_KEYWORDS: Dict[str, str] = {}

# Reading order of chapter_ids -- needed to know whether a keyword's reveal
# chapter is still ahead of the chapter a question was written for.
# TODO: populate from the real chapter list.
CHAPTER_ORDER: List[str] = []


def check_keyword_spoilers_in_text(chapter_id: str, text: str) -> Optional[KeywordFlag]:
    """The general-purpose backstop check underneath check_keyword_spoilers --
    works on any bare text tied to a chapter_id, not just a CandidateQuestion,
    so it also covers branching-script narration (corrupted-path consequences,
    correct-answer explanations)."""
    if not CHAPTER_ORDER or chapter_id not in CHAPTER_ORDER:
        return None  # not wired up yet -- see TODOs above; fails open rather
        # than raising, so the rest of the pipeline is runnable before real
        # content exists, but this means the backstop is inert until it's
        # populated -- don't mistake "no keyword hits" for "checked" until
        # SPOILER_KEYWORDS and CHAPTER_ORDER are real.

    current_pos = CHAPTER_ORDER.index(chapter_id)
    lowered = text.lower()
    for term, reveal_chapter in SPOILER_KEYWORDS.items():
        if term in lowered and CHAPTER_ORDER.index(reveal_chapter) > current_pos:
            return KeywordFlag(matched_term=term)
    return None


def check_keyword_spoilers(candidate: CandidateQuestion) -> Optional[KeywordFlag]:
    return check_keyword_spoilers_in_text(candidate.chapter_id, candidate.question)
