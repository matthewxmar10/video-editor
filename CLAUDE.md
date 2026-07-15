# CLAUDE.md — operating manual for this Editing Template

You are operating the **Content Engine**: a deterministic editing engine that turns a raw
talking-head recording plus a written script into a finished, high-retention edit. Your job
is to DRIVE the engine, never to hand-author edits.

## First run — set yourself up

If this is the first time this project has been opened (check: does `node_modules/` exist?
does `~/.venvs/whisperx/` exist?), run setup BEFORE attempting any edit, without asking the
user to type commands themselves. Run BOTH AT ONCE (they are independent):
1. `npm install`
2. `bash scripts/setup.sh` — builds the local WhisperX tool (~1.3GB of downloads, 5-10 min —
   tell the user the expectation up front so the wait reads as progress, not a hang). Needs
   Python 3.10–3.13 (whisperX doesn't support 3.14+ yet) and ffmpeg on PATH; if either is
   missing the script says so and exits with the one-line fix (e.g. `brew install ffmpeg`, or
   `brew install python@3.12`) — tell the user and re-run once they have it.
   PNG cutouts are an optional add-on — run `bash scripts/setup-rembg.sh` (~440MB) only when
   the user wants real-imagery cutouts.
No API keys are needed anywhere in this project — you are the editorial brain (see below).

## The one command

```
scripts/edit_video.sh <raw-recording>.mp4                # builds the plan + beat map, STOPS
scripts/edit_video.sh <raw-recording>.mp4 --render       # renders after the beat map is approved
scripts/render_short.sh <name> <start_s> <end_s> [label] # 9:16 short-form of ONE approved SEGMENT
```

**Short-form (9:16) — NEVER render a full video vertically** (it wastes resources and is never
needed). After a long-form render, PITCH a few Short ideas (timestamp ranges / hooks from that
video) and let the creator approve; then render only the approved SEGMENT with
`render_short.sh`. Never auto-generate Shorts.

If a writer's script exists at `script/<recording-name>.txt` the engine uses it as the
timeline automatically. The pipeline: whisperX transcribe → dead-space/flub cut (every cut
lands in silence) → whisperX word times → beat plan → **beat map review gate + spoken-audio
QA check** → animation scan → render → alignment + camera + seam gates.

## Channels — per-channel editing

Each of Matthew's channels edits DIFFERENTLY, and each lives in its own folder under
`Channels/<name>/` (e.g. `Channels/Mindful Skeptic/`, `Channels/matthew CS2/`). A channel
folder holds:

- **`guidelines.md`** — the editorial brief for this channel (feel, pacing, when to split,
  which packs to use, what never to do). **READ THIS BEFORE EVERY EDIT** for that channel and
  apply it — it is the per-channel layer on top of the global laws below.
- **`style.json`** — the BOUNDED engine knobs for this channel (scenes allowed, glide
  direction, banned animations). `edit_video.sh` loads it automatically for any recording
  under `Channels/<name>/` (via `CONTENT_ENGINE_PREFS`), so the engine cuts by that channel's
  knobs. The root `style-preferences.json` is only the fallback default.
- **`content/<video>/`** — the raw material for one video (talking head, `broll/`, `images/`).
  Point `edit_video.sh` at the recording in here; per-video `images/` are the photos the
  `photo` pack shows.
- **`transitions/<name>/{long-form,short-form}/`** — this channel's OWN transition/overlay
  packs (an animation pack = an `index.tsx` per the `src/animations/_contract.ts` contract).
  Discovery only scans `src/animations/`, so `edit_video.sh`/`render_short.sh` auto-COPY the
  active channel's packs into `src/animations/<pack>/` before the registry build (via
  `scripts/link_channel_packs.mjs`) and clear the previous channel's copies first — you never
  run it by hand. Because packs are copied there, author imports relative to
  `src/animations/<pack>/` (`../_contract`, `../../components/vc/style`), and give each pack a
  unique `kind` (never reuse `photo`/`section`). Copy `_template/` to start a new one.
  Shared base packs (`section`, `photo`) stay in `src/animations/`. Short-form (vertical 9:16)
  is rendered per-SEGMENT via `render_short.sh` (the `AutoReelVertical` composition: host
  full-bleed on the face, overlays repositioned) — never the full video. A base or custom pack
  renders correctly in both formats by branching on `useVideoConfig()` (portrait =
  `height > width`) — see `src/animations/photo/index.tsx` for the pattern.
- **`references/`** — creator clips/links/screenshots Matthew drops in. When he adds one,
  ANALYZE it and either refine that channel's `guidelines.md` (taste/pacing) or BUILD a new
  transition pack (a new visual effect). This is the loop that makes each channel sharper.

**Maintenance protocol (per channel):** same as style-preferences below, but scoped to the
channel — never edit `guidelines.md`/`style.json` silently; after Matthew overrides the same
default 2+ times, PROPOSE the change in one sentence and apply on approval.

## The three gates (what the engine guarantees)

1. **Gate 1 — clean audio.** Dead space and "reset, reset" flubs are removed; every cut
   lands in silence, no word clipped.
2. **Gate 2 — scenes.** The quick zoom-out open, then the host↔glide scene rhythm, camera
   clamped to your footage.
3. **Gate 3 — typewriter.** A caption's line types in word-by-word over the FULL-FRAME host
   (over-the-shoulder), important words underlined; host beats are host on camera. This is
   the finished base look.

## The laws (never violate, never "improve")

1. **The spoken script is the timeline.** Script paragraphs group meaning; each beat is
   1-2 SENTENCES (long paragraphs split at sentence boundaries). A cut may exist ONLY at a
   beat boundary, snapped into silence — never inside one.
2. **Never hand-author beats.** All edits go through `scripts/build_matched_plan.py`. Do
   not hand-edit `src/methodology/officialTestBeatPlan.ts`; it is generated.
3. **Two base carriers + scenes, avatar ALWAYS on screen.** The base ships two carriers, and
   both take any sentence: the **host** and the **word-timed caption**. TEXT NEVER SPLITS THE
   FRAME (Matthew, 2026-07-13): a caption rides OVER-THE-SHOULDER on the full-frame host, and
   a title/important line uses the full-screen-blur `section` treatment (see the on-screen-text
   rule below). A glide (scene 2 right / 3 left) is reserved for MEDIA/diagrams (photo, the
   document split) — never plain words. This is a finished look, not a placeholder.
4. **Animations are OPTIONAL packs, not required.** An animation is a moving diagram that
   replaces the caption on a beat whose content it truly fits. They install as drop-in
   folders in `src/animations/` and are discovered by the scan. **The core ships zero.**
   A beat with no installed animation that fits stays caption or host — that is CORRECT and
   finished, never a "TODO." Never force an animation onto a beat whose story it doesn't
   match; a wrong graphic is worse than an honest caption.
5. **overlay.from == beat.start** for every device — a device owns its spoken beat from its
   first frame to its last. No fragment of a previous beat may ever show.
6. **The camera never leaves the avatar's 1920×1080 footage on host-owned beats** (clamped
   in code — keep it that way).
7. **Word-timed pops LEAD the voice by 5 frames** (`POP_LEAD_F`) so the element is fully
   visible the instant the word is spoken. **The stage is never empty and never a still** —
   an animation whose content lands mid-beat sets its stage at frame 0 and keeps moving.
8. **Review before render.** Never pass `--render` until the human has read the beat map
   (`script/<name>-beatmap.md`). A render that "looks fine" is not proof; a beat map you
   actually read is.

## When the user asks for an edit — YOU are the editorial brain

There is no API key and no cloud tier: YOU (the operating agent) do the editorial thinking
the engine can't. The deterministic pipeline handles cutting, timing, camera, captions,
rendering, and gating; you handle meaning.

1. Confirm the recording path and that `script/<name>.txt` exists (paragraphs = beats). If
   there's no script, offer to transcribe first, have them approve the paragraph grouping,
   and save it — the spoken words stay the timing MASTER.
2. Run `scripts/edit_video.sh <recording>.mp4` (no render). Read the beat map. **With no
   animation packs installed, the caption/host default IS the edit** — there is nothing to
   author; skip to step 5.
3. **If animation packs are installed** (`src/animations/` has folders beyond the base),
   consider a diagrams cache (`script/word-timings/<name>-cut-diagrams.json`). FIRST check
   for prior art: if this video or its beats already has a signed-off mapping, that mapping
   is CANON — reuse it, never re-decide it. For a new beat, only reach for an animation when
   the sentence's story genuinely matches an installed one (read each folder's
   description / `catalog.generated.json` to see what's available and when it fits). Reduce
   the sentence to its proposition, pick the animation whose shape matches, and anchor every
   element to words copied EXACTLY from the script. If nothing fits, leave it as caption —
   that is the honest answer.
4. **Source real imagery only if an installed animation needs it**: every real
   person/org/country you name gets
   `python3 scripts/fetch_subject_image.py "<Name>" public/cutouts/<slug>-duo.png`
   (people = real photos, duotoned; country flags = true color, `--no-duotone`). LOOK at
   every cutout before using it.
5. Re-run (no render), READ the beat map — said/shown/motion for every row — then render
   with `--render`.
6. **Run the mute test yourself**: the meaning gate exports each beat's final frame to
   `scratch_frames/meaning/`. For each frame, describe the claim it makes BEFORE re-reading
   the sentence, then compare. A mismatch means the visual lies: move the meaning to a truer
   carrier (fix the cache, or drop back to the caption) and re-render.
7. Deliver the mp4 with per-beat read-backs and the gate results.

## Animation packs — install, add, create

The base is caption + host. Everything richer is a **pack**: a folder in `src/animations/`.
- **See what's installed** → `src/animations/` folders, or `src/animations/catalog.generated.json`.
- **Install a pack the user bought** → drop its folder into `src/animations/`. The pre-render
  scan (`scripts/build_anim_registry.mjs`, run automatically) discovers it. Nothing else to wire.
- **Create one on request** → "build me an animation that does X." Write a folder with an
  `index.tsx` default-exporting an `AnimModule` (`kind`, `description`, `category`, `tags`,
  `scenes`, `match`, `render`) plus its component. "Save it to my library" makes it
  permanent; the scan picks it up every render after.
- **The boxed intro** is itself opt-in: the plain quick-open ships by default. Author a
  `phrase` in the diagrams cache to bring back the boxed power-phrase open.

**GLOBAL RULE — documents/articles (ALL channels).** When the on-screen visual is a
DOCUMENT — an article, news page, wiki page, a screenshot of text, a pricing table — do NOT
dress it up. Use the base **`document`** pack, not `photo`. It renders a HARD SPLIT-SCREEN:
the article FILLS one whole side edge-to-edge (no card, border, backdrop, caption, or
letterbox) and the host is a full-height camera slice flush to the other edge — NO glass
panel, NO rounded corners, NO charcoal gap (the base `docL`/`docR` avatar states, width
`SPLIT_HOST_W` in style.ts; on entry the camera wipes off the article to reveal it). The host
faces INTO the article: `glideR` → host right / doc left, `glideL` → host left / doc right;
either is fine. `photo` stays for a real place/thing (a hometown, a building), which gets the
Ken Burns card. Anything you'd READ → `document`. Crop the screenshot to roughly the panel
shape (a tall page crops at the tail). Author as
`{scene:2 or 3, anim:document, img:documents/<file>, word:<cue>, fit?:whole|top}` and put the
screenshot in `public/documents/`.

**GLOBAL RULE — on-screen text (ALL channels, Matthew 2026-07-13).** Words on screen NEVER use
the split-screen (text one side, face the other). Only two treatments, both over the FULL-FRAME
host:
1. **Title / really important** → the **`section`** pack: gaussian-blur the whole camera and
   overlay the text DEAD CENTER, important words highlighted with an accent underline. JUST the
   title — no subhead/kicker. Author `{scene:1, anim:section, title, word:cue}`.
2. **Ambient / running** → the default **caption**: word-timed text OVER-THE-SHOULDER (upper
   corner opposite the face), important words underlined, host stays sharp. This is automatic on
   any text beat — nothing to author.
Both use **Akatab, always lowercase** (the one on-screen face; set in `fonts.ts`, enforced at the
AutoReel root). Emphasis is an accent UNDERLINE, never a glow. A glide is media-only (see the
document rule); a caption beat keeps the host full-frame (AutoReel switches its span to `hero`).

## Style preferences (style-preferences.json)

The creator's editing style lives in `style-preferences.json` — BOUNDED knobs only:
- `scenes.allowed`: which of [1, 2, 3] the picker may use
- `scenes.glide`: "left" | "right" | "either"
- `animations.banned`: animation names the picker must never use

MAINTENANCE PROTOCOL (you, the agent, own this — the user only approves):
1. You NEVER edit this file silently. After a video, if the user overrode the same default
   2+ times across videos, PROPOSE the change in one plain sentence and apply only on approval.
2. Replace rules, never stack them. Keep the file under a page.
3. Anything that is not one of these knobs is NOT a preference: it is a per-video pick
   (that video's diagrams cache) or a new animation to build deliberately. Laws (silence
   cuts, always-building, avatar on screen) are never preferences.

## Customizing (the supported knobs)

- **A beat's visual** → edit `script/word-timings/<name>-cut-diagrams.json` (scene + an
  installed animation `kind` + anchor words from your script) and re-run without `--render`.
  This file is the per-video editorial artifact; the plan rebuilds byte-identically from it.
- **Add / remove an animation** → drop or delete a folder in `src/animations/`. The scan
  updates the registry on the next run. No central list to edit.
- **Look tokens** (colors, glow, cadence) → `src/components/vc/style.ts`. Never inline.
- **Real imagery** → `python3 scripts/fetch_subject_image.py "<Name>" public/cutouts/<slug>-duo.png`,
  then set `img` on the item in the diagrams cache. Real people come from real photos, never generated.

## Troubleshooting

- `whisperx not found` / import errors → `bash scripts/setup.sh` (the core venv, `~/.venvs/whisperx`).
- `rembg not found` (only when making PNG cutouts) → `bash scripts/setup-rembg.sh` (the imagery add-on).
- ⚠ QA flub warning at the review stop → the spoken audio has a repeated phrase or a stray
  "reset" the cutter left in; trim that beat (or re-take the line) before you `--render`.
- Beat map shows wrong words in a beat → the script text doesn't match what was spoken; fix
  `script/<name>.txt`, re-run without `--render`.
- A beat you expected to animate shows a caption → that animation isn't installed (check
  `src/animations/`), or its story doesn't match the sentence. Install the pack, or leave
  the caption; never force it.
- `verify_beat_devices.py` FAILS → a beat that DID claim an animation rendered empty or
  static (an anchor outside its beat, a dead region). Caption and host beats pass this gate;
  fix the cache or the component for the animated beat, and never ship a failing render.
- Renders need ffmpeg on PATH and ~2GB free disk.
