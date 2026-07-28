# role_play_read

Spoiler-safe literary-analysis question pipeline for the character role-play
feature: per chapter, per assigned character, generates candidate questions
using full-book knowledge, then gates each one through a knowledge-restricted
reviewer before anything reaches a human's approval screen.

## The three roles

- **C (`generator.py`)** — sees the full play text. Writes candidate
  questions for a character at a given chapter, drawing on complete
  knowledge of the whole play.
- **B (`gate.py`)** — sees *only* the text through the current chapter, plus
  the bare question. Judges whether answering it would require knowledge the
  reader doesn't have yet. Never sees C's prompt, reasoning, or even that a
  generator exists.
- **A (`orchestrator.py`)** — plain code, not an LLM call. Calls C, then
  calls B once per candidate in a fresh, separate context, merges in the
  deterministic keyword backstop (`keyword_gate.py`), and flags anything
  that isn't a confident CLEAR for human review.

Each role is an independent, stateless API call — see the module docstrings
in `gate.py` and `orchestrator.py` for why that isolation, not shared
conversation state, is what actually keeps the spoiler gate meaningful (and
for the honest limitation: restricting *context* doesn't erase what the
underlying model already knows from training, which is why the gate is a
mitigation layered with a deterministic backstop and human review, not a
standalone guarantee).

## What's real vs. placeholder right now

- Pipeline logic, data model, and the isolation guarantee: real, and tested
  (`tests/test_isolation.py` checks structurally that B's calls never
  contain C's context, not just that the code is commented that way).
- `AnthropicClient`: real implementation, **not yet run against a live key**
  — treat it as unverified until it's actually exercised, same as any other
  new integration.
- `SPOILER_KEYWORDS` / `CHAPTER_ORDER` in `keyword_gate.py`: empty
  placeholders. The backstop fails open (flags nothing) until these are
  populated with real chapter IDs and terms — don't mistake "no keyword
  hits" for "checked" until then.
- Full play text and chapter chunking: not wired up. `run_pilot.py` has
  placeholders showing where they go.
- The spoiler policy (`spoiler_policy.py`) — broad tragic outcome is
  acceptable background, specific plot mechanics are not — is the one
  editorial decision baked in; change the wording there if the policy
  itself needs to change.

## Recommended next step

Run the pilot on one chapter by hand before automating across the whole
play:

```bash
pip install -r requirements.txt --break-system-packages
export ANTHROPIC_API_KEY=...
# fill in FULL_PLAY_TEXT and PILOT_CHAPTER in run_pilot.py first
python run_pilot.py
```

Read through what gets flagged vs. what passes clean, and check it against
your own judgment — this is the same "validate on one chapter before
running it across the whole book" step discussed for the pipeline generally.
Tune `SPOILER_POLICY` wording, B's prompt in `gate.py`, or the flag
threshold based on what you actually see, not in the abstract.

## Not yet connected

This pipeline is offline / content-authoring only, matching the "AI
proposes, human approves" pattern used elsewhere in this project — it isn't
wired into any live student-facing app yet. Where the review screen and the
actual role-play chat surface live (immersive_reader's frontend, a new
project, etc.) is still an open question.
