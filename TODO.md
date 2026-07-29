# TODO / known gaps

## Next up (explicitly requested)
- **Beat-level spoiler isolation.** `ScriptBeat` narration currently does
  NOT go through role B individually — only each checkpoint's
  `corrupted_narration` and `correct_explanation` do (see
  `script_generator.py`'s module docstring, and the "Known gap" section of
  `README.md`). This is a real gap, not a cosmetic one: a beat could in
  principle reveal something that happens *later in the same scene*, and
  the existing gate only checks "has the reader finished this chapter" —
  chapter granularity, not within-scene position. Fixing this needs a
  design for finer-grained isolation, most likely passing role B something
  like "the beats already shown in this script, up to this point" instead
  of (or alongside) `chapters_read_so_far`, plus deciding how far back
  isolation is needed — is it just "not yet in the play," or also "not yet
  in *this specific script's* narration order so far"? Worth resolving
  before this scales past a single hand-checked pilot scene.

## Also open (carried over, not newly discovered)
- ~~Runtime attempt-tracking state machine~~ — **done**, in
  `checkpoint_runtime.py`: canonical choice passes immediately (with
  `correct_explanation` shown to every student as reinforcement); a wrong
  choice shows a ~30-second `corrupted_narration` and re-presents the same
  checkpoint with that option removed, so the worst case is trying both
  wrong options before the one remaining (correct) option is left. This
  superseded the earlier "restart the whole scene" design. Still just pure
  decision logic, not wired into a live chat surface — that part is still
  open.
- `SPOILER_KEYWORDS` / `CHAPTER_ORDER` in `keyword_gate.py` are still empty
  placeholders — the deterministic backstop is inert until populated.
- `AnthropicClient` is real code but has never been run against a live key
  in this environment.
- The thin teacher UI (`{grade, passage_text}` submission) is unscoped —
  no frontend exists yet for this project.
