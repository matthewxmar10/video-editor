// ─────────────────────────────────────────────────────────────────────────────
// STARTER TEMPLATE for a channel transition pack. Copy this whole folder, rename it
// to your pack's name (e.g. `whip`, `statbar`, `killfeed`), and edit below. The engine
// auto-copies Channels/<channel>/transitions/<pack>/long-form/ into src/animations/<pack>/
// at edit time (scripts/link_channel_packs.mjs), so:
//   • Author imports EXACTLY as below — '../_contract', '../../components/vc/style' —
//     they resolve from src/animations/<pack>/ after the copy, same as a base pack.
//   • Set `kind` to your folder name. It must be unique (don't reuse 'photo'/'section').
//   • This _template folder is skipped by discovery (leading underscore) — it never renders.
//
// This example is a lower-third LABEL CHIP that pops on a spoken cue word, works in both
// 16:9 and 9:16 (portrait branch), and keeps moving across the beat (the always-building law).
// Delete what you don't need.
// ─────────────────────────────────────────────────────────────────────────────
import React from 'react';
import { interpolate, spring, useCurrentFrame, useVideoConfig } from 'remotion';
import type { AnimModule, AnimContext } from '../_contract';
import { GOLD, glow, CREME_DARK } from '../../components/vc/style';
import { SANS } from '../../components/vc/fonts';

const POP_LEAD_F = 5; // pops start this many frames BEFORE the cue word (the POP_LEAD law)

// The per-beat data your pack reads, authored in the diagrams cache
// (script/word-timings/<name>-cut-diagrams.json), e.g.:
//   { "scene": 1, "anim": "templatepack", "title": "Your text", "word": "cue" }
// `word` is copied EXACTLY from the script; the plan builder resolves it to a time `at`.
type PackData = { title: string; at: number; label?: string };

const TemplateChip: React.FC<AnimContext> = ({ b, start, f }) => {
  const frame = useCurrentFrame();                 // 0 at the beat's first frame
  const { fps, width, height } = useVideoConfig();
  const portrait = height > width;                 // 9:16 short-form vs 16:9 long-form
  const data = (b as unknown as { templatepack?: PackData }).templatepack;
  if (!data) return null;

  // Voice-led entrance: fully in a hair BEFORE the cue word is spoken.
  const local = f(data.at) - start - POP_LEAD_F;
  const p = spring({ frame: frame - local, fps, config: { damping: 200, stiffness: 210, mass: 0.6 }, durationInFrames: 12 });

  // ALWAYS-BUILDING: after it lands it never freezes — a slow drift + breathing accent keep
  // real motion in every third of the beat (the build gate samples each third).
  const t = frame / fps;
  const drift = Math.sin((t * Math.PI * 2) / 3.0) * 5;
  const breathe = 0.4 + 0.22 * Math.sin((t * Math.PI * 2) / 2.2);

  return (
    <div style={{ position: 'absolute', inset: 0, display: 'flex', justifyContent: 'center',
      alignItems: 'flex-end', paddingBottom: portrait ? 420 : 232, pointerEvents: 'none' }}>
      <div style={{
        opacity: p,
        transform: `translateY(${(1 - p) * 26 + drift}px) scale(${interpolate(p, [0, 1], [0.96, 1])})`,
        position: 'relative', maxWidth: portrait ? 900 : 1180, padding: '26px 54px 30px',
        borderRadius: 26, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12,
        backgroundColor: 'rgba(18,18,20,0.42)',
        backdropFilter: 'blur(22px) saturate(115%)', WebkitBackdropFilter: 'blur(22px) saturate(115%)',
        border: `1px solid ${glow(0.22)}`, boxShadow: '0 26px 60px rgba(0,0,0,0.5)',
      }}>
        {data.label ? (
          <div style={{ fontFamily: SANS, fontWeight: 800, fontSize: 30, letterSpacing: '0.30em',
            textTransform: 'uppercase', color: GOLD.yellow,
            textShadow: `0 0 22px ${glow(breathe)}` }}>{data.label}</div>
        ) : null}
        <div style={{ fontFamily: SANS, fontWeight: 800, fontSize: portrait ? 54 : 66,
          letterSpacing: '-0.02em', color: CREME_DARK.ink, lineHeight: 1.02, textAlign: 'center' }}>
          {data.title}
        </div>
      </div>
    </div>
  );
};

const mod: AnimModule = {
  kind: 'templatepack',                 // ← rename to your folder name (must be unique)
  description: 'STARTER TEMPLATE — a lower-third label chip that pops on a spoken cue word. Replace this description with a precise "use me when…" so the device picker offers your pack only when the sentence truly fits. Author as {scene, anim:<kind>, title, label?, word:cue}.',
  category: 'template',                 // ← e.g. 'structure' | 'data' | 'flow' | 'brand'
  tags: ['template'],                   // ← finer content-type hints the picker filters on
  scenes: ['host', 'glide'],            // ← where it may render: 'host' (over full-frame host) and/or 'glide' (open panel)
  match: (b) => !!(b as unknown as { templatepack?: unknown }).templatepack,  // ← match your data key
  render: (c) => <TemplateChip {...c} />,
  priority: 100,                        // lower = matched first when two packs could both fit
};

export default mod;
