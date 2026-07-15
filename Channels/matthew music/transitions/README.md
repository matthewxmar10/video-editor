# matthew music — transitions & templates

Each transition/template is a folder here with a version per media type:

    <transition-name>/
      long-form/     # 16:9 (1920x1080)  — built & renderable today
      short-form/    # 9:16 (1080x1920)  — rendered per-segment by `render_short.sh` (never full-length)

A transition is an animation pack: an `index.tsx` that default-exports an `AnimModule`
(see src/animations/_contract.ts). Shared base packs used by every channel live in
src/animations/ (currently: `section` title cards, `photo`). Put channel-specific ones here.

To add one: drop a reference in ../references/ and ask me to build it (or ask directly).
`_template/` shows the long-form/short-form folder layout.

## How a pack here actually renders (the wiring)

Discovery scans `src/animations/` only. So at edit time the engine **auto-copies this
channel's packs into `src/animations/<pack>/`** and rebuilds the registry — done by
`scripts/link_channel_packs.mjs`, called from `edit_video.sh` (long-form) and
`render_short.sh` (short-form). You don't run it by hand. On the next edit it clears the
previous channel's copies first, so channels never leak packs into each other.

Because a pack is **copied** into `src/animations/<pack>/`, author its imports relative to
THAT location — `'../_contract'`, `'../../components/vc/style'` — exactly like a base pack.
`_template/long-form/index.tsx` is a working starter chip; copy the `_template` folder,
rename it to your pack name, set `kind` to match, and edit.

**Formats.** One `long-form/index.tsx` that branches on `useVideoConfig()` (portrait =
`height > width`) renders BOTH 16:9 and 9:16 — that's the default; short-form falls back to
it. Add a `short-form/index.tsx` only when you want a genuinely different vertical build.
Pack names must be unique and must not reuse a base pack name (`photo`, `section`).
