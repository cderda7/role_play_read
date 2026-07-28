"""
Example entry point for running the pipeline against ONE chapter -- this is
the pilot step recommended before running it across the whole play: check
the flag rate and B's actual judgment against your own on a single chapter
before trusting it at scale.

This is a starting point, not a finished CLI -- fill in real content and
run it by hand, read through review_items, and see whether the gate's calls
match your own judgment before doing anything more automated.

Usage (once ANTHROPIC_API_KEY is set in the environment):
    python run_pilot.py
"""

from roleplay import AnthropicClient, Chapter, orchestrate_chapter

# TODO: replace with the real text. Keeping this short and act1_scene1-only
# for the pilot -- see the module docstring above.
FULL_PLAY_TEXT = """\
PASTE THE FULL PLAY TEXT HERE (or load it from a file) -- this is what role
C, the generator, is allowed to see.
"""

PILOT_CHAPTER = Chapter(
    chapter_id="act1_scene1",
    order=0,
    text="PASTE ACT 1, SCENE 1's TEXT HERE -- this is what role B, the gate, is allowed to see.",
)


def main() -> None:
    client = AnthropicClient()  # requires ANTHROPIC_API_KEY in the environment

    review_items = orchestrate_chapter(
        full_play_text=FULL_PLAY_TEXT,
        chapters_read_so_far=[PILOT_CHAPTER],
        character="Juliet",
        client=client,
    )

    flagged = [item for item in review_items if item.needs_review]
    print(f"{len(review_items)} questions generated, {len(flagged)} flagged for review.\n")

    for item in review_items:
        marker = "FLAGGED" if item.needs_review else "clear"
        print(f"[{marker}] ({item.question.focus}) {item.question.question}")
        if item.needs_review:
            if item.gate_result.verdict != "CLEAR":
                print(f"    gate: {item.gate_result.verdict.value} -- {item.gate_result.reasoning}")
            if item.keyword_flag is not None:
                print(f"    keyword hit: {item.keyword_flag.matched_term!r}")
        print()


if __name__ == "__main__":
    main()
