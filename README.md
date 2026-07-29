# role_play_read

Spoiler-safe content pipeline for the character role-play feature, built on
the real text of *Romeo & Juliet* (Project Gutenberg #1513, modern spelling,
chunked into 24 real Act/Scene chapters). Two things get authored per
chapter + character + grade level, both through the same spoiler-gated
pipeline:

- **Q&A** (`generator.py` / `orchestrator.orchestrate_chapter`) — a flat
  list of literary-analysis questions.
- **Branching role-play script** (`script_generator.py` /
  `orchestrator.orchestrate_scene_script`) — narration beats interleaved
  with decision checkpoints, where a wrong choice shows a short in-scene
  consequence rather than a long divergent story.

## The three roles

- **C** (`generator.py` for questions, `script_generator.py` for scripts) —
  sees the full play text. Writes candidate content for a character at a
  given chapter, drawing on complete knowledge of the whole play, calibrated
  to a grade level (7-12).
- **B** (`gate.py`) — sees *only* the text through the current chapter, plus
  the bare text being judged (a question, or a piece of narration). Judges
  whether it would require knowledge the reader doesn't have yet, and where
  possible suggests an open-ended rephrase/revision that keeps the
  analytical intent without the spoiler. Never sees C's prompt, reasoning,
  or even that a generator exists.
- **A** (`orchestrator.py`) — plain code, not an LLM call. Calls C, then
  calls B once per candidate/narration item in a fresh, separate context,
  merges in the deterministic keyword backstop (`keyword_gate.py`), and
  flags anything that isn't a confident CLEAR for human review.

Each role is an independent, stateless API call — see the module docstrings
in `gate.py` and `orchestrator.py` for why that isolation, not shared
conversation state, is what actually keeps the spoiler gate meaningful (and
for the honest limitation: restricting *context* doesn't erase what the
underlying model already knows from training, which is why the gate is a
mitigation layered with a deterministic backstop and human review, not a
standalone guarantee).

## Content-authoring heuristics

- **Character selection** (`character_selector.py`) — the student's
  character each scene is chosen automatically by "most plot points",
  operationalized as `turns x quartile_breadth`: number of speaking turns,
  weighted down if those turns are all clustered in one part of the scene.
  Validated against two cases: Act I Scene I picks BENVOLIO (not Romeo, who
  wins on raw word count; not Sampson, who wins on nothing), and Act IV
  Scene V picks the NURSE (not Peter, whose comic musician banter is
  clustered at the very end and wins on raw turn count alone).
- **Checkpoint density** (`checkpoint_density.py`) — scenes at or above 1400
  words get 2 major / 5+ minor checkpoints; shorter scenes get 1 major / 3+
  minor. The threshold was picked from the real 24-scene word-count
  distribution, not guessed.
- **Timing target** (`timing.py`) — a rough playtime estimate (read-aloud
  pace + a flat per-checkpoint decision allowance) checked against the
  explicit minimums: 3 minutes for a standard scene, 5 for a complex one,
  assuming a student who answers every checkpoint correctly on the first
  try. This is a tripwire for "too short, add more content" during review,
  not a precise prediction.
- **Grade calibration** — every generated question and every script's
  narration is written for a specific grade (7-12), threaded through to C's
  prompt and stored alongside the content for traceability. B's spoiler
  judgment deliberately does *not* depend on grade.

## The branching script, concretely

A `SceneScript` (`script_models.py`) is an ordered list of `ScriptBeat`
(2-5 sentences of plain narration) and `Checkpoint` items. Each `Checkpoint`
has a prompt and a small set of `CheckpointOption`s, exactly one marked
`is_canonical`. Every non-canonical option carries a `corrupted_narration` —
a short, spoiler-gated consequence that ends the attempt quickly rather than
branching into a long alternate story. Every checkpoint also carries a
`correct_explanation` — also spoiler-gated — for why the canonical choice is
correct.

**This package only authors that content offline.** The actual attempt
tracking — first wrong choice at a checkpoint shows `corrupted_narration`
and restarts the scene; getting the *same* checkpoint wrong a second time
skips straight to `correct_explanation` instead of corrupting again — is
per-student session state that belongs to a future interactive runtime, not
this pipeline. See `script_models.py`'s module docstring for the full
runtime/authoring boundary.

**Known gap:** only `corrupted_narration` and `correct_explanation` go
through the spoiler gate. Plain `ScriptBeat` text does not get its own gate
call — see `script_generator.py`'s module docstring for why that's a
deliberate scoping choice (it would need finer-grained "what's already been
narrated in *this* script" isolation, not just chapter-level) rather than an
oversight.

## What's real vs. placeholder right now

- Pipeline logic, data model, and the isolation guarantee for both the Q&A
  and branching-script pipelines: real, and tested structurally
  (`tests/test_isolation.py`, `tests/test_script_isolation.py` check that
  B's calls never contain C's context, not just that the code is commented
  that way).
- Real play text and real chapter chunking: done (`data/romeoandjuliet.txt`,
  `data/chapters.json`, `chunk_play.py`, regression-tested in
  `tests/test_chunk_play.py`).
- Character selection, checkpoint density, timing estimate: implemented and
  tested against known-good cases.
- `AnthropicClient`: real implementation, **not yet run against a live key**
  — treat it as unverified until it's actually exercised.
- `SPOILER_KEYWORDS` / `CHAPTER_ORDER` in `keyword_gate.py`: empty
  placeholders. The backstop fails open (flags nothing) until these are
  populated with real chapter IDs and terms — don't mistake "no keyword
  hits" for "checked" until then.
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
python run_pilot.py               # defaults to act1_scene1, grade 9
python run_pilot.py act2_scene2 10
```

Read through what gets flagged vs. what passes clean, and check it against
your own judgment. Tune `SPOILER_POLICY` wording, B's prompt in `gate.py`,
or the flag threshold based on what you actually see, not in the abstract.
`run_pilot.py` currently exercises the Q&A pipeline; wiring the same
chapter/character/grade through `orchestrate_scene_script` for a script
pilot is a natural next addition.

## Not yet connected

This pipeline is offline / content-authoring only, matching the "AI
proposes, human approves" pattern used elsewhere in this project — it isn't
wired into any live student-facing app yet. Where the review screen and the
actual role-play chat surface live (immersive_reader's frontend, a new
project, etc.), and where the runtime attempt-tracking state machine for the
branching script lives, are still open questions.
