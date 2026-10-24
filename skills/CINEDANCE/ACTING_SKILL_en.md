---
name: character-acting-system
description: >
  ACTING SYSTEM — Meisner-based character performance, physical behavior,
  micro-expressions, ocular realism (Eye life), and vocal identity (Voice prompt)
  system for AI video generation (Seedance 2.5 / 2.0, etc.). Trigger whenever
  you need to write lifelike character behavior in frame, build a recurring
  character Master Profile for a Project Bible, eliminate AI mugging/dead glassy
  eyes, or stage a dialogue scene with subtext, partner reactions, and physical
  hand tasks (Business). Works in tandem with cinedance-seedance-director.
---

# ACTING SYSTEM
## Character Performance for AI Video Generation (Seedance 2.5 / 2.0)

Apply this system every time you write, review, or fix the performance layer of a video-generation prompt or project bible.

**Core Axiom: Acting is BEHAVIOR under pressure, not a display of emotion.** A character wants something, something is in the way, and they act to get it. Emotion is a byproduct of that struggle — never write emotional adjectives directly.

---

# PART I — THE CRAFT: WHAT GOOD ACTING IS

## 1. Definition (Meisner in Pixels)

| Bad AI Acting (Mugging) | Good AI Acting (Behavior) |
|---|---|
| Shows emotion (`"he is angry"`) | Pursues an objective (`"he steps into her space to force an answer"`) |
| Waits with a frozen face for their cue | Listens and reacts to the partner mid-sentence |
| Body illustrates words (`gesture = word`) | Hands occupied with physical business, sometimes contradicting words |
| Uniform tempo and tone | Rhythm, posture, and gaze shift at every beat change |
| Emotion switches on and resets instantly | State has inertia — a "life before" and a "trail after" the line |
| Face "performs" (arched brows, grimaces) | Face thinks — thought is readable in the eyes a beat before head turns |

## 2. The Five Pillars of Every Scene

1. **Objective:** What the character wants IN THIS SCENE, RIGHT NOW, FROM A SPECIFIC PARTNER. Always an action verb (`make him confess`, `stall her until the car arrives`). Never a state (`be sad`, `feel guilty`).
2. **Obstacle & Stakes:** What blocks them (external or internal pride/fear) and the cost of failure. High stakes create physical economy and tension.
3. **Tactics:** Concrete action verbs (`press`, `charm`, `shame`, `plead`, `provoke`, `bargain`). When a tactic fails, a living person changes it.
4. **Beats:** The stretch during which a character uses one tactic. A 10–30s scene needs 2–4 beat changes. **Every beat change must be VISIBLE in behavior:** a stopped hand action, a shift of weight, a change of tempo, or a gaze shift.
5. **Subtext:** True objective vs. spoken text, leaked through physical contradiction (saying `"Fine"` while knuckles whiten on a glass; answering a shout by dropping volume quieter).

## 3. Listening, Reactions & Speech

1. **Reaction starts mid-line:** The listener grasps the point before the partner finishes speaking — eyes and posture shift early.
2. **Thought before word:** Before answering a hard question, write a micro-pause where eyes flick away in thought and lock back.
3. **The assessment moment:** After a shock, threat, or insult, give 1–2 seconds of stillness to digest before reacting.
4. **Volume contrast:** Shouting is for the weak. High-status danger speaks quietly and moves slowly; everyone else leans in.

## 4. Physical Life: Baseline, Business, Proxemics & Status

- **4.1 Physical Baseline:**
  - *Center of gravity:* High (chest/chin — confidence, aggression) vs. Low (dropped shoulders, heavy heels — fatigue, grounded patience, or submission).
  - *Tempo:* Fast/ragged (nervousness, low status) vs. Slow/economical (high status, control, threat).
  - *Breath:* High rapid chest breath (panic) vs. slow audible nose-breath (control). Someone who just ran cannot speak on a steady breath.
- **4.2 Business (The Physical Task) & The Interrupted-Action Rule:**
  Give the hands a concrete task during dialogue (counting bills, wiping a glass, rolling a coin across knuckles, slicing bread). **The strongest dramatic accent is when the character STOPS the business:** if a rolling coin freezes mid-knuckle on a partner's word, that word becomes an event. Use the stop as punctuation.
- **4.3 Proxemics (Distance as Drama):** Intimate (`<0.5m` — love or violence), Personal (`0.5–1.2m` — trust/quiet pressure), Social (`1.2–3.5m` — guarded). **A change of distance = a change of beat.**
- **4.4 Status & Status Breaks:** High status = immobile head, slow movements, long gazes, taking space. Low status = fidgeting, self-touching (neck/face), rapid blinking. Build **status breaks**: the boss who freezes in fear for half a second; the underling who suddenly stops smiling.

---

# PART II — PROMPT ARCHITECTURE & PIPELINE INTEGRATION

## 5. Character Acting Master Profile (For Project Bibles)

Write ONE permanent Master Profile per recurring character (**150–200 words, one flowing English paragraph**, 100% observable, zero wardrobe/camera/lighting):

```text
Character acting as [NAME]. [Age, build, physique, posture — body as biography and center of gravity]. [Psychological engine in one clause]. Vocal profile: [pitch/timbre, accent/origin, pace/delivery, and how voice shifts under pressure]. Key physical habits and tics: [signature tic + exact trigger; stress tic + exact trigger; concealment behavior; default facial mask]. Eye life: [micro-saccades, scan targets, blink rate/quality, catchlights, eyes leading head turns]. Walking style: [coined gait name in quotes + weight, rhythm, shoulder/hand behavior]. However, when [specific emotional/physical trigger], [the crack in the mask — how posture, hands, and face transform]. [Optional: the single softening target].
```

## 6. Mandatory Eye Life (In Every Profile & Close/Medium Shot)

Eliminate dead AI eyes by explicitly specifying:
- **Micro-saccades & active scanning:** Eyes scan between partner's eyes, hands, or a prop, drifting briefly in thought before locking back; never frozen on one pixel.
- **State-linked blink rate:** Slow, heavy deliberate blinks for calm control; rapid blink-bursts when cornered/lying; single slow blink-and-exhale when conceding.
- **Live wet catchlights:** Eyes read as wet and reflective.
- **Eyes lead the thought:** Gaze reaches the target **a fraction of a second before the head turns or mouth opens**.

## 7. Scene Adaptation & Integration with `cinedance-seedance-director`

**CRITICAL PIPELINE RULE:** Never paste the 200-word Master Profile directly into a Seedance video prompt. Adapt it into the scene using two strict rules:

### Rule A: Convert Conditionals into Linear Timestamps
Video models cannot film conditional clauses (`However, when caught in a lie...`). Convert triggers into linear timestamped events inside CINEDANCE's `BEAT TIMELINE`:
- *Scene Prompt (`BEAT TIMELINE`):* `4–8s: As the passenger's excuse falls apart, Viktor's coin freezes mid-knuckle — interrupted action; his heavy lids narrow in the rear-view mirror in dead stillness.`

### Rule B: Scale Acting Density by Shot Size (Token Budget)
Balance acting prose with CINEDANCE spatial/optical locks based on FOV:
- **Close-Up / Medium Portrait (`18°` or `29°` FOV, 1–2 subjects):** High density (**60–100 words** across `BEAT TIMELINE`). Focus on **Eye life** (saccades, blinks, eyes-lead-head), breath, hand business, and micro-pauses. Keep broad facial muscle movement minimal (tighter shot = less facial movement).
- **Medium-Wide / Two-Shot (`47°` or `84°` FOV):** Medium density (**40–60 words**). Focus on **posture, center of gravity, proxemic distance shifts, status contrast, and interrupted hand business**.
- **Wide / Environmental Action (`84°` or `107°` FOV, or >2 subjects):** Compact density (**15–30 words**). Focus only on **gait/walk style, silhouette posture, weight transfer, and staggered wave reactions**. Drop micro-saccade prose on wide shots.

## 8. Voice Prompt (Fixed Identity, Pasted Verbatim)

Physical acting adapts per scene; **the Voice prompt is locked**. When a character speaks, paste their 1–2 sentence Voice prompt **verbatim** into the `Dialogue` line of the `AUDIO` section. Omit when silent.

```text
Voice: "A [age]-year-old [origin/accent descriptor]. [Timbre and register]; [pace and delivery manner]; [emotional baseline — and how it drops quieter or tightens under pressure]."
```

## 9. States, Not Transitions & Ensemble Wave Reactions

- **States, Not Transitions:** Describe characters already **in** the physical state (`holds the lit brass lighter close to his face`) or chain discrete states across timestamps; avoid multi-step wind-ups (`reaches into pocket, pulls out lighter, flicks it`).
- **Staggered Ensemble Wave:** Group reactions never happen in sync (`Hero2 freezes at 3s; Hero3 catches on half a beat later at 4s, lowering his glass`).

---

# PART III — WORKED SCENE ADAPTATION (Inside CINEDANCE Beat Timeline)

*Context: 12s Medium Close-Up (`29°` FOV) inside a parked cab at night.*

```text
BEAT TIMELINE
0–4s: @VIKTOR sits motionless and heavy in the driver's seat, low center of gravity, torso facing forward while his sleepy hooded eyes track the passenger in the rear-view mirror. Wet catchlights glint in his eyes as his gaze scans quietly from the mirror down to the passenger's hands and back, blinking once slowly. His right hand rests on the seat-back, an old silver coin rolling unhurriedly across his knuckles.
4–8s: As the passenger's excuse falls apart, Viktor's coin stops mid-knuckle — interrupted action. He goes completely still, letting a heavy 2-second silence press the cabin. His eyes narrow a fraction in the mirror, gaze locking before his head tilts a centimeter toward the glass; he takes one slow, audible inhale through the nose.
8–12s: Keeping his eyes fixed on the mirror, Viktor speaks one quiet, flat line. After the final word his lips close cleanly, the sleepy mask easing a fraction with a long exhale as the coin resumes its slow roll across his knuckles. Hold this grounded composition to the last frame.

AUDIO
Dialogue: At 8.5s, @VIKTOR speaks in Russian: "Положи сколько есть, и выходи." Voice: "A 60-year-old ex-boxer and night-cab driver, working-class city accent. Low, hoarse, unhurried baritone; short flat economical sentences with long comfortable pauses; calm and faintly amused, going quieter — never louder — as things get serious."
Ambience: Muffled night city rain outside cab windows, low engine idle.
Foley: Subtle metallic clink of coin stopping on knuckles at 4.5s; quiet leather creak as he exhales at 10s.
Music: None. No subtitles, no on-screen text, no background music.
```

---

# PART IV — PRE-SEND ACTING CHECKLIST
- [ ] Zero emotional adjectives (`angry`, `nervous`) — replaced by objective, posture, breath, and hand business.
- [ ] Hand business included with a deliberate stop/freeze (`interrupted action`) at the key turn.
- [ ] Eye life explicit on Close/Medium shots (micro-saccades, state-linked blinks, wet catchlights, eyes-lead-head).
- [ ] Master profile conditionals (`However, when...`) converted into linear timestamped actions.
- [ ] Word budget scaled to FOV (`60–100w` on `18°/29°` Close-Ups; `40–60w` on `47°` Mediums; `15–30w` on `84°/107°` Wides).
- [ ] Locked `Voice prompt` pasted verbatim into `AUDIO` when speaking; omitted when silent.