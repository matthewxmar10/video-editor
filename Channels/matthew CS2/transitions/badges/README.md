# CS2 stream badges — standalone overlay clips

Three drop-in overlay "toasts" for the CS2 highlight edits (Renyan-style). These are
**not** beat-driven animation packs — they're self-contained transparent clips you drag
onto a timeline in your editor. Each animates **in → holds ~2.5s → out** on its own (4.0s
total), with the sound baked in.

## The clips (`out/`)

| File | Colour | Text | Sound | Default position |
|------|--------|------|-------|------------------|
| `cs2-badge-twitch-recording.mov` | Twitch violet | `recorded live on twitch` (+ pulsing live dot, AK-47 + Scythe of Vitur bookends facing inward) | recorder-start: clunk + motor whir + warm REC beep | upper area |
| `cs2-badge-subscribe.mov` | YouTube red | `subscribe` | bright two-tone ding | centre |
| `cs2-badge-join-discord.mov` | Discord blurple | `join the discord` | short poppy blip | lower third |

Format: **ProRes 4444, 1920×1080, 30fps, straight alpha** (`yuva444p12le`), stereo PCM
audio. Drops onto any timeline (Premiere / DaVinci / FCP) with transparency intact — lay it
over the gameplay, no keying needed.

## Rebuild / tweak

```
Channels/matthew CS2/transitions/badges/build_badges.sh
```

Synthesizes the audio, renders the three comps to transparent ProRes 4444, and muxes. Edit:
- **Look / motion / text** → `render/Badges.tsx` (one `<Badge>` per clip; `anchorY` sets the
  vertical position, `0`=top … `1`=bottom).
- **Weapon art** → `assets/ak47.png`, `assets/scythe.png` (the build stages them to
  `public/badges/` for Remotion's `staticFile`).
- **Sounds** → `render/synth_audio.py` (the `twitch` / `subscribe` / `discord` recipes).
- **Colours / glass / glow** → `render/style.ts`.

Rendered by a **separate Remotion entry** (`render/index.ts`) so the engine's talking-head
AutoReel pipeline is untouched.

## Notes
- The Twitch clip is larger (~104MB) because the detailed weapon imagery carries more detail
  through ProRes 4444; the other two are ~28MB.
- Want a badge at a different screen position (corner instead of centre)? It's a one-line
  `anchorY` change + re-run — ask and I'll re-render.
