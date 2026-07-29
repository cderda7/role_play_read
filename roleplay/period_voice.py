"""
Voice/dialect guidance for checkpoint option quotes, kept in its own file on
purpose (SRP): script_generator.py's job is deciding the SceneScript's
STRUCTURE (beats, checkpoints, options, corrupted narrations, explanations)
-- it has no business also owning a hardcoded opinion about what dialect or
register those options are written in. That's a property of the specific
book being adapted, not of the branching-script pipeline itself.

To wire up a different novel/reading:

  - If it's written in a distinctive historical or stylized voice (like
    this project's Elizabethan/Early Modern English), write a new
    `..._VOICE_GUIDANCE` constant here, following the same shape as
    ELIZABETHAN_VOICE_GUIDANCE below, and pass it as generate_scene_script's
    `voice_guidance` argument (or as orchestrate_scene_script's, which
    forwards it).
  - If it's in standard contemporary English, NO_SPECIAL_VOICE_GUIDANCE is
    the right default -- script_generator.py already falls back to it, so
    a caller adapting a plain modern-English book doesn't need to touch
    this file at all.

Nothing in this file is spoiler-related and nothing here is gated -- it's
purely a style instruction injected into role C's prompt, same as grade-level
calibration.
"""

from __future__ import annotations

# For Romeo & Juliet (and any other Early Modern English text): every
# checkpoint option, canonical and non-canonical alike, should read as a
# genuine in-character line in the play's own period voice, not a modern
# paraphrase of one.
ELIZABETHAN_VOICE_GUIDANCE = (
    "EVERY option's label (canonical and non-canonical alike) must be a "
    "genuine in-character line in the play's own Early Modern English "
    "voice -- thee/thou/thy, period vocabulary and syntax -- not a modern "
    "paraphrase. Format each label the same way: a brief action "
    "description, then a colon, then the quoted in-character line, e.g. "
    '\'Match his heat with your own: "Have at thee then, and gladly, since '
    "thou'lt have it so.\"' A student should be choosing between three "
    "period-voiced lines, not one quote and two summaries."
)

# The default for a book in standard contemporary English -- no historical
# dialect to reproduce, just a natural, in-character line in the book's own
# narrative voice.
NO_SPECIAL_VOICE_GUIDANCE = (
    "Each option's label should be a natural, in-character line of dialogue "
    "or action description written in this book's own narrative voice -- "
    "not a flattened, generic summary of the choice."
)
