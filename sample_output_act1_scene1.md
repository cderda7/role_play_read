# Act I, Scene I — Sample branching script output (v2)

**This is a hand-simulated walkthrough, not a live pipeline run.** There's
still no `ANTHROPIC_API_KEY` configured in this environment. I wrote role
C's script content myself, staying tight to the real scene text, and
simulated role B's gate verdicts by applying the same spoiler-policy
judgment B is instructed to apply. Every number below (playtime estimate,
per-narration time-budget check, the worst-case retry trace) was computed
by actually running this content through `timing.py` and
`checkpoint_runtime.py`, not eyeballed.

**What changed since v1:** every option — not just the canonical one — now
carries a genuine in-character Early Modern English line, not a modern
paraphrase. And the checkpoint interaction model itself changed: a wrong
choice no longer corrupts the whole scene and forces a restart. It shows a
short (~30 second) consequence and re-presents the *same* checkpoint with
that option removed. `correct_explanation` is shown to every student who
passes, as reinforcement, not held back for someone who got it wrong first.

**Chapter:** act1_scene1 &nbsp;|&nbsp; **Character (auto-selected):** BENVOLIO
&nbsp;|&nbsp; **Grade:** 9 &nbsp;|&nbsp; **Density:** 2 major / 5+ minor
(complex — 2088 words) &nbsp;|&nbsp; **Estimated playtime:** 7.4 min via
`timing.estimate_minutes()` (target: 5 min minimum for a complex scene —
clears it comfortably) &nbsp;|&nbsp; **All 14 corrupted narrations checked
against the ~30s / 65-word budget — none exceed it** (longest is 14.3s).

---

## Beat 1
Sampson and Gregory, Capulet's men, are spoiling for a fight — trading crude
jokes about biting their thumbs at any Montague who crosses them. When Abram
and Balthasar happen by wearing Montague colors, the insults turn direct,
and swords start coming out of their sheaths.

## 🔶 Checkpoint 1 — MAJOR (`act1_scene1_cp0`)
**Prompt:** You round the corner and find Sampson and Gregory squared off
against two of your uncle's men, blades already drawn. What do you do?

- ✅ **Canonical** — *"Part, fools! Put up your swords; you know not what
  you do."*
- ❌ *"Have at thee then, and welcome to thy grave, thou Capulet dog!"*
  - **(gate: CLEAR, 13.8s):** You wade in swinging instead of parting them.
    The brawl only grows louder, and by the time Tybalt storms onto the
    street, it's you standing mid-fight with a blade raised.
- ❌ *"Nay, let them spend their heat; this quarrel is not mine to mend."*
  - **(gate: CLEAR, 10.2s):** You hold back, arms crossed. The scuffle
    drags on without you, and it's your hesitation the Prince's guard
    notices, not your restraint.

**Correct explanation (gate: CLEAR), shown once you pick right:** Benvolio's
defining trait in this scene is that he steps in only to separate the
fighters, sword drawn but never swung in anger.

**Worst-case trace, run for real through `checkpoint_runtime.CheckpointAttempt`:**
1. Pick "Have at thee..." → CORRUPTED, shown its consequence, checkpoint
   re-presented with that option gone. Two choices remain.
2. Pick "Nay, let them spend their heat..." → CORRUPTED again, shown its
   consequence, re-presented again. Only the canonical option is left.
3. The canonical line is now the only choice → PASSED, `correct_explanation`
   shown.

A student who picks the canonical line first try skips straight to step 3
— they never see the two branches above at all.

## Beat 2
You beat their swords down just as Tybalt storms onto the street, blade
already bared, itching for a reason to use it on a Montague.

## 🔹 Checkpoint 2 — MINOR (`act1_scene1_cp1`)
**Prompt:** Tybalt turns on you: *"Turn thee, Benvolio, look upon thy
death."* How do you answer?

- ✅ **Canonical** — *"I do but keep the peace; put up thy sword, or manage
  it to part these men with me."*
- ❌ *"As much I hate thee, Tybalt, as I hate hell and all thy kindred
  too!"*
  - **(gate: CLEAR, 14.3s):** You match his heat with your own. By the time
    the citizens arrive with their clubs, it's two drawn swords they see
    first, not one man trying to calm the street.
- ❌ *"I'll not bandy words with thee, nor blade neither."*
  - **(gate: CLEAR, 11.5s):** You turn to go, and Tybalt reads it as exactly
    the insult he was hoping for. He closes the distance before you've
    taken three steps.

**Correct explanation (gate: CLEAR):** Even under a direct threat, Benvolio
asks for peace rather than escalating — he offers the olive branch first
and fights only once Tybalt attacks anyway.

## Beat 3
Tybalt attacks anyway, and swords are out again. Citizens pour in with
clubs, shouting for both houses' blood; then Capulet, Lady Capulet,
Montague, and Lady Montague all arrive wanting to join in. Finally Prince
Escalus storms in, furious, and orders every weapon to the ground on pain
of death — this is the third such brawl, he says, and the next one will
cost lives. Everyone but you and your aunt and uncle disperses.

## 🔹 Checkpoint 3 — MINOR (`act1_scene1_cp2`)
**Prompt:** Your uncle turns to you: *"Speak, nephew, were you by when it
began?"* What do you tell him?

- ✅ **Canonical** — *"Here were the servants of your adversary, and yours,
  close fighting ere I did approach."*
- ❌ *"'Twas the servants' quarrel, good uncle; I did but happen by."*
  - **(gate: CLEAR, 8.3s):** Montague presses for more detail anyway, and
    now you're explaining the fight twice — once badly, once honestly.
- ❌ *"In truth, mine uncle, I saw not how it did begin."*
  - **(gate: CLEAR, 11.1s):** Your uncle frowns — half of Verona saw you in
    the middle of it. The vague answer costs you his trust in the retelling.

**Correct explanation (gate: CLEAR):** The text has Benvolio give a
detailed, accurate account unprompted — matter-of-fact honesty is how he's
established as a reliable narrator.

## Beat 4
The street empties. Lady Montague, relieved Romeo wasn't caught up in the
brawl, asks after him. Your uncle admits Romeo's been withdrawn for weeks —
shutting himself in his room by day, wandering alone by night — and no one
can get him to say why. Then Romeo himself appears in the distance. Your
aunt and uncle step aside to let you try.

## 🔶 Checkpoint 4 — MAJOR (`act1_scene1_cp3`)
**Prompt:** Romeo's within earshot now, looking as low as your uncle
described. Do you go to him?

- ✅ **Canonical** — *"See, where he comes. So please you step aside; I'll
  know his grievance or be much denied."*
- ❌ *"'Tis not my place to pry where he would keep his counsel close."*
  - **(gate: CLEAR, 12.9s):** You hold back, giving him room. He drifts
    past toward the city gate without a word, and whatever's weighing on
    him stays exactly as locked away as before.
- ❌ *"Come, good uncle, let us all make merry with my cousin here!"*
  - **(gate: CLEAR, 7.4s):** Romeo, who's been guarding this closely from
    everyone, only closes off further with an audience watching.

**Correct explanation (gate: CLEAR):** Benvolio is the one who insists on
getting Romeo alone and asking directly — that's what makes the private
conversation that follows possible at all.

## Beat 5
You catch up with Romeo. He's full of the kind of elaborate contradictions
lovesick teenagers specialize in — "O brawling love, O loving hate," "cold
fire, sick health" — clearly more heartsick than he's willing to just say
plainly.

## 🔹 Checkpoint 5 — MINOR (`act1_scene1_cp4`)
**Prompt:** Romeo asks, half-joking, *"Dost thou not laugh?"* at his own
overwrought speech. How do you respond?

- ✅ **Canonical** — *"No, coz, I rather weep."*
- ❌ *"Ha! Thou speak'st in riddles fit to make a jester weep for envy!"*
  - **(gate: CLEAR, 10.6s):** You laugh, and Romeo's face closes up. He'll
    keep talking, but the warmth's gone out of it — he's performing now,
    not confiding.
- ❌ *"Enough of sighs, good cousin — what say you to some breakfast?"*
  - **(gate: CLEAR, 8.3s):** Romeo goes along with it, relieved, and the
    conversation you were hoping to have quietly closes back up.

**Correct explanation (gate: CLEAR):** Benvolio's actual line is
sympathetic, not dismissive — he takes Romeo's lovesickness seriously even
while gently needling him later.

## Beat 6
Romeo admits, in his roundabout way, that he's in love — and that it's
unrequited. You press him to just say who.

## 🔹 Checkpoint 6 — MINOR (`act1_scene1_cp5`)
**Prompt:** Romeo deflects your first attempt with a joke: *"Shall I groan
and tell thee?"* Do you push further?

- ✅ **Canonical** — *"Groan? Why, no; but sadly tell me who."*
- ❌ *"'Tis no matter of mine to know a heart so shut."*
  - *Corrupted narration, first draft (gate: **SPOILER** — flagged:
    "Friar Laurence's letter will later fail to reach Romeo before the
    tomb"):* ~~This foreshadows how Friar Laurence's letter will later fail
    to reach Romeo before the tomb.~~ *(Rejected — names a specific plot
    mechanic from Act V that hasn't happened yet in what's been read.)*
  - **Revised (gate: CLEAR, 6.9s):** You let it go — Romeo seems almost
    relieved, but whatever's actually eating at him stays exactly as
    unresolved as before you asked.
- ❌ *"Is it Livia, cousin? Or Rosamund, or fair Helena?"*
  - **(gate: CLEAR, 9.7s):** Romeo waves you off — you've made his private
    ache into a guessing game, and he's not interested in playing along.

**Correct explanation (gate: CLEAR):** The text has Benvolio keep gently
pressing — *"Groan? Why no, but sadly tell me who"* — until Romeo actually
answers.

*(Kept this one deliberately: my first draft of that corrupted narration
reached forward into Act V. Catching and rewriting it before it ships is
exactly what role A's review step is for. Note the flagged/rejected text
never appears in the final option — the "guess her name" option also
carefully avoids the real name, Rosaline, since she isn't established by
name in this chapter's own text yet either.)*

## Beat 7
Romeo tells you: he loves a woman who's sworn to stay chaste and will never
love him back. He's miserable about it, and starting to look for a way to
end the conversation.

## 🔹 Checkpoint 7 — MINOR (`act1_scene1_cp6`)
**Prompt:** Romeo says *"Farewell, my coz"* and starts to go. Do you let
him?

- ✅ **Canonical** — *"Soft! I will go along; and if you leave me so, you do
  me wrong."*
- ❌ *"Go then, sweet coz, and nurse thy grief alone; I'll trouble thee no
  further."*
  - **(gate: CLEAR, 7.8s):** Whatever advice you meant to offer goes
    unsaid, and he's left to stew in it without company.
- ❌ *"Nay, tarry — what think you of the Prince's decree?"*
  - **(gate: CLEAR, 6.9s):** He's already too far off to hear, and the
    moment for real advice has passed.

**Correct explanation (gate: CLEAR):** Benvolio explicitly refuses to let
Romeo wander off alone — his last lines are advice delivered precisely
because he stays and keeps talking.

## Beat 8 (closing)
You walk with him, urging him to look at other women instead of pining for
one who's sworn him off. Romeo insists it's impossible. You're unconvinced,
and tell him so as the scene ends: *"I'll pay that doctrine, or else die in
debt."*

---

### Review-screen summary (simulated)
- **7 checkpoints** (2 major, 5 minor) — matches the density model exactly.
- **21 gate calls**: 14 corrupted-branch narrations (2 wrong options × 7
  checkpoints) + 7 correct-answer explanations.
- **1 flagged** on first pass (checkpoint 6's first wrong option), revised
  and re-verified clean.
- **Timing:** 7.4 min estimated vs. a 5 min target for a complex scene —
  clears it with room to spare.
- **Time-budget check:** all 14 corrupted narrations run under the ~30s
  cap; longest is 14.3s (checkpoint 2's "meet fire with fire" option).
- **Every option, canonical and wrong, is a genuine in-character quote now**
  — no modern paraphrases left anywhere in the checkpoint labels.
