# Mindful Skeptic — editing guidelines

> Matthew's channel about religion, deconstruction, and skepticism (formerly under the
> "Mind on Religion" name — that name is retired, don't put it on screen or in outros).
> I read this before every edit for this channel.

## Format
- **Long-form:** ~13–17 min talking-head explainers/stories, 16:9. This is the current default.
- **Short-form:** 9:16 Shorts cut from the long-form per-segment via `render_short.sh` (never a full vertical render).

## Feel & pacing
- Calm, thoughtful, personal. **Mostly the face** — this is a talking-head channel, so the
  honest default is you on camera. Do NOT overdo "retention editing."

## Camera & framing
- **Default = full-face (scene 1)** with the gentle push-in. Aim ~85–90% of beats on face.
- Left/right split (scene 2/3 caption) **only when you're talking data or numbers.**
- `face_x ≈ 1030` for the podcast set (you sit slightly right of center). Footage is 2560×1440.

## Captions & text
- Light. Percentages render correctly now (write "78%", not "seventy-eight percent").
- Fillers (um/uh) are stripped from captions automatically.
- A beat that opens with a >0.6s pause before your first word stays on FACE (a caption there
  would flash an empty panel).

## Transitions & overlays (packs)
- **`section` (base pack):** small title + soft blur over your face when you enter a clearly
  numbered/named section ("point 1, point 2"). Use on **explainer** videos with explicit
  points; **do NOT** use on personal-narrative videos (they have no "point 1/2/3").
- **`photo` (base pack):** host glides aside, a real photo fills the panel (Ken Burns +
  caption chip). Use when you **name a real place/thing** — hometown, a church, your school.
  Photos for a video go in its `content/<video>/images/` folder; true color, not duotoned.

## Music & sound
- You wanted soft background music — the engine has **no music support yet**. Currently
  shipping without music (your call, 2026-07-12). Revisit when music support is built.

## Bounded knobs
- See ./style.json. Scenes 1/2/3 all allowed, glide either — but the "mostly face, data-only
  split" policy above is what I actually apply (it's editorial judgment, not a hard knob).

## Never do
- Never put "Mind on Religion" on screen or say it in the outro. Keep "My name is Matthew."
- No forced animation on a beat whose story doesn't match — an honest face beat beats a wrong graphic.

## History / delivered
- `Skep_Leaving` (Why Christianity is failing in the US) and `Skep_Story` (your deconstruction
  story) were the first two edits (2026-07-12). Their raw is currently in `raw/Skepticism/`;
  going forward, new videos go in `./content/<video>/`.
