"""
Entry point for running the pipeline against ONE chapter -- the pilot step
recommended before running it across the whole play: check the flag rate
and B's actual judgment against your own on a single chapter before
trusting it at scale.

Now wired up to the real data (data/romeoandjuliet.txt, data/chapters.json)
and the character-selection heuristic, rather than placeholder text -- the
only thing left to fill in is a real ANTHROPIC_API_KEY.

COST: role C resends the whole play (~45k tokens) on every call, which
dominates the price of a single-chapter run. Prompt caching (see
llm_client.py's module docstring) is wired up here via cache_ttl="1h" --
the FIRST run in a session pays full price once to write the cache, and
every run after that, for any chapter, reuses it at ~10% of the base input
price as long as it happens within that hour. Running several chapters
back-to-back in one sitting is meaningfully cheaper than spreading them out
past an hour apart.

Usage:
    export ANTHROPIC_API_KEY=...
    python run_pilot.py                  # defaults to act1_scene1, grade 9
    python run_pilot.py act2_scene2 10   # chapter_id, grade_level
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from roleplay import AnthropicClient, Chapter, orchestrate_chapter
from roleplay.character_selector import select_character
from roleplay.checkpoint_density import checkpoint_density

DATA_DIR = Path(__file__).parent / "data"


def load_chapters() -> list[Chapter]:
    raw = json.loads((DATA_DIR / "chapters.json").read_text(encoding="utf-8"))
    return [Chapter(chapter_id=c["chapter_id"], order=c["order"], text=c["text"]) for c in raw]


def load_full_play_text() -> str:
    return (DATA_DIR / "romeoandjuliet.txt").read_text(encoding="utf-8")


def main() -> None:
    target_chapter_id = sys.argv[1] if len(sys.argv) > 1 else "act1_scene1"
    grade_level = int(sys.argv[2]) if len(sys.argv) > 2 else 9

    chapters = load_chapters()
    chapters_by_id = {c.chapter_id: c for c in chapters}
    if target_chapter_id not in chapters_by_id:
        raise SystemExit(f"Unknown chapter_id {target_chapter_id!r}. Known: {sorted(chapters_by_id)}")

    target = chapters_by_id[target_chapter_id]
    # Everything read so far includes every chapter up to and including the
    # target, in reading order -- that's what defines what role B knows.
    chapters_read_so_far = [c for c in chapters if c.order <= target.order]

    character = select_character(target.text)
    density = checkpoint_density(target.text)
    print(
        f"Chapter: {target_chapter_id}  |  Character (auto-selected): {character}  |  "
        f"Grade: {grade_level}  |  Density: {density.major} major / {density.minor_min}+ minor "
        f"({'complex' if density.is_complex else 'standard'})\n"
    )

    # cache_ttl="1h" (rather than the default 5-minute cache) because the
    # realistic pilot workflow is: run one chapter, actually read the
    # flagged output, decide whether to tweak a prompt, then run the next --
    # that easily takes longer than 5 minutes per chapter. The 1-hour cache
    # costs 2x to write (vs. 1.25x for 5-minute) but every call in the same
    # session that reuses the ~45k-token play-text prefix pays only 0.1x for
    # it once cached, so it pays for itself well before a second chapter.
    client = AnthropicClient(cache_ttl="1h")  # requires ANTHROPIC_API_KEY in the environment
    full_play_text = load_full_play_text()

    review_items = orchestrate_chapter(
        full_play_text=full_play_text,
        chapters_read_so_far=chapters_read_so_far,
        character=character,
        grade_level=grade_level,
        client=client,
    )

    flagged = [item for item in review_items if item.needs_review]
    print(f"{len(review_items)} questions generated, {len(flagged)} flagged for review.\n")

    for item in review_items:
        marker = "FLAGGED" if item.needs_review else "clear"
        print(f"[{marker}] ({item.question.focus}) {item.question.question}")
        if item.needs_review:
            if item.gate_result.verdict.value != "CLEAR":
                print(f"    gate: {item.gate_result.verdict.value} -- {item.gate_result.reasoning}")
            if item.keyword_flag is not None:
                print(f"    keyword hit: {item.keyword_flag.matched_term!r}")
            if item.gate_result.suggested_rephrase:
                verified = (
                    item.rephrase_gate_result.verdict.value if item.rephrase_gate_result else "not re-checked"
                )
                print(f"    suggested rephrase ({verified}): {item.gate_result.suggested_rephrase}")
        print()


if __name__ == "__main__":
    main()
