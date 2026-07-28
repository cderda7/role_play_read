"""
The one explicit policy call from the design discussion: what counts as
acceptable "broadly known" background vs. an actual spoiler. Shared verbatim
between B's (gate) and C's (generator) prompts so they're operating from the
same rule instead of each inferring their own version of it.

This is a real editorial decision, not a technical default -- change the
wording here if the policy itself should change, rather than tuning it
separately in gate.py and generator.py.
"""

SPOILER_POLICY = (
    "Policy: the broad fact that this is a tragedy and that Romeo and "
    "Juliet both die is treated as common cultural knowledge, not a "
    "spoiler -- it's fine to reference even before the text has shown it. "
    "What counts as an actual spoiler is the SPECIFIC plot mechanics: the "
    "potion plan, Friar Laurence's letter failing to arrive, the exact "
    "sequence of events at the tomb, or Paris being present there. Treat "
    "those, and anything similarly specific, as off-limits before the text "
    "has established them."
)
