# The Motion Library — the base motion and how packs extend it

Every visual in the engine derives its timing from your spoken words. Nothing is keyframed
by hand, so every asset re-times itself to any script. This file explains the **base
motion** that ships in the core, and how **animation packs** add to it.

## The base: two carriers, always on the avatar

Every spoken beat (1-2 sentences) gets exactly ONE scene, and the avatar is ALWAYS on
screen. The core ships two visual carriers, and both work on any sentence:

| Carrier | What it looks like |
|---|---|
| **Host** | Full-frame you, with the camera doing one deliberate move (the quick open, or a slow push). |
| **Typewriter caption** | You glide to a side panel; your spoken line types into the open half word-by-word, the emphasis word glowing yellow. |

That is the whole base look, and it is a finished look, not a placeholder. Talking-head
video is mostly you talking, so the honest default is your words on screen and the host
carrying the rest. A beat that has no better carrier stays caption or host, and that is
correct.

## The open (the hook)

The first beat opens with a **quick zoom-out**: it starts tight on your face and snaps out
to the natural frame in about 0.65s, right as your first word lands, then hands into the
glide. It is a fast visual hook, not a slow drift. (The boxed power-phrase intro is an
opt-in upgrade, not the default. See "Packs" below.)

## The scene rhythm

With no pack telling it otherwise, beats rotate in a fixed host↔glide pattern
(`open → glide → host → glide → host …`, glide side alternating), so the avatar keeps
moving and you never get two static host beats in a row. This is structural: same script
in, same edit out.

## Animations are optional PACKS (drop-in folders)

An **animation** is a moving diagram that replaces the caption on a beat whose content it
truly fits (a count, a growth curve, a list collapsing to one). The core ships **zero
animations** — they install as packs.

A pack is a self-contained folder in `src/animations/<kind>/`. The engine **scans that
folder before every render** (`scripts/build_anim_registry.mjs`) and uses whatever is
installed. So:

- **See what's installed** → look in `src/animations/`, or read
  `src/animations/catalog.generated.json` (the scan writes it: each animation's name, its
  "use me when…" description, its category and tags).
- **Add a pack** → drop its folder into `src/animations/` (or ask Claude to add it). The
  next render discovers it automatically. No list to hand-edit.
- **Remove one** → delete its folder. It's gone on the next render.

There is no fixed "library of ten." What you can use is whatever folders are present. The
description that decides when each one fits lives inside its folder, so the list can never
drift from what's actually installed.

## When a pack IS installed, its animation obeys these laws

1. **Word-timed, voice-led** — pops start 5 frames before their word (`POP_LEAD_F`) so the
   element is fully visible the instant it's voiced.
2. **Always-building** — the animation starts on the beat's first frames and assembles
   toward its final state until the last word. A 7-second beat means 7 seconds of building,
   never a finished object floating for the back half. The gate samples motion in every
   third of every beat and fails a dead stretch.
3. **One camera move per appearance** — a single directional move easing to a stop, or a
   continuous slow push. Never two moves in a row, never a rubber-band.
4. **Canvas-locked on host beats** — the camera never exposes anything beyond your
   1920×1080 footage (clamped in code).
5. **overlay.from == beat.start** — a device owns its whole spoken beat; no fragment of a
   neighboring beat can ever show.
6. **One look** — all colors, glow, and type come from `src/components/vc/style.ts`
   (charcoal grid + #F7C715 yellow glow + one sans, emphasis = glowing yellow).
7. **Big glows are radial halos** (`haloBg`, `ellipse closest-side`), never large
   box-shadow blurs (Chromium rasterizes huge shadow blurs with square edges).

## Real imagery beats icons (for packs that show subjects)

Any pack item naming a real person, team, or thing can carry `img` — a duotone cutout
rendered instead of an icon. Sourcing is one command:
`python3 scripts/fetch_subject_image.py "Christian Pulisic" public/cutouts/pulisic-duo.png`
(your `assets/people/` folder wins → Wikipedia lead image → Commons search; then automatic
background removal + brand duotone). Universal symbols (red card, checkmark, X) stay as
glyphs; they read faster than photos.

## Base primitives (always present)

`AvatarGlide` (the host camera + glide spine) · `KineticCaption` (the word-by-word
typewriter caption) · `IntroStage` (the opt-in boxed intro asset) · `ZoomPan` (eased
camera) · `CharcoalBg` (the constant charcoal grid).

## Building a pack (or a custom animation)

Each animation is a folder with an `index.tsx` that default-exports one `AnimModule`
(`kind`, `description`, `category`, `tags`, `scenes`, `match`, `render`) plus its
component. Ask Claude: "build me an animation that does X, and save it to my library."
Claude writes the folder and the scan picks it up. That is how packs, and your own
vibe-created animations, become permanent.
