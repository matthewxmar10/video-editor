// SECTION / TITLE — Matthew's mode-1 text treatment (ALL channels, 2026-07-13): a title or a
// really-important line is shown by GAUSSIAN-BLURRING the whole camera and overlaying the text
// DEAD CENTER, with the important words highlighted by an accent UNDERLINE. The host stays on
// camera (scene 'host'), just defocused behind the title — NEVER a split-screen with text on one
// side and the face on the other. Akatab, always lowercase.
//
// DATA: the plan carries `section: { title, at }` on the beat (authored in the diagrams cache:
// {"scene":1,"anim":"section","title":"aging out","word":"first"}). Just the title — no subhead
// (Matthew, 2026-07-13). `at` is the spoken cue word's time; the title LEADS the voice by
// POP_LEAD_F so it is fully readable the instant the word lands.
import React from 'react';
import { interpolate, spring, useCurrentFrame, useVideoConfig } from 'remotion';
import type { AnimModule, AnimContext } from '../_contract';
import { GOLD, glow, CREME_DARK } from '../../components/vc/style';
import { SANS } from '../../components/vc/fonts';

const POP_LEAD_F = 5; // the title starts this many frames BEFORE the cue word (the POP_LEAD law)

const SectionTitle: React.FC<AnimContext> = ({ b, start, f }) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const portrait = height > width;
  const sec = (b as unknown as { section?: { title: string; at: number; label?: string } }).section;
  if (!sec) return null;

  // Voice-led entrance: the blur + title are fully in a hair before the cue word is spoken.
  const local = f(sec.at) - start - POP_LEAD_F;
  const p = spring({ frame: frame - local, fps, config: { damping: 200, stiffness: 200, mass: 0.6 }, durationInFrames: 14 });
  // ALWAYS-BUILDING: after it lands, a slow breathe + drift keep it alive (and the blurred host
  // keeps moving behind it), so no third of the beat is a frozen still.
  const t = frame / fps;
  const drift = Math.sin((t * Math.PI * 2) / 3.2) * 4;
  const titleSize = portrait ? 92 : 128;

  return (
    <div style={{ position: 'absolute', inset: 0, display: 'flex', justifyContent: 'center', alignItems: 'center', pointerEvents: 'none' }}>
      {/* GAUSSIAN BLUR over the WHOLE screen — defocuses the host camera behind the title, with a
          gentle dark scrim so the text is legible over any footage. Fades in with the title. */}
      <div style={{
        position: 'absolute', inset: 0,
        backdropFilter: `blur(${Math.round(26 * p)}px) saturate(108%)`,
        WebkitBackdropFilter: `blur(${Math.round(26 * p)}px) saturate(108%)`,
        backgroundColor: `rgba(12,12,14,${0.44 * p})`,
      }} />
      {/* JUST the title, DEAD CENTER — no subhead (Matthew, 2026-07-13). Important text
          HIGHLIGHTED WITH AN ACCENT UNDERLINE. */}
      <div style={{
        position: 'relative', opacity: p, transform: `translateY(${(1 - p) * 26 + drift}px) scale(${interpolate(p, [0, 1], [0.96, 1])})`,
        maxWidth: portrait ? 940 : 1500, textAlign: 'center',
        fontFamily: SANS, fontWeight: 800, fontSize: titleSize, lineHeight: 1.04, letterSpacing: '-0.02em',
        textTransform: 'lowercase', color: CREME_DARK.ink,
        textDecorationLine: 'underline', textDecorationColor: GOLD.yellow,
        textDecorationThickness: Math.max(5, Math.round(titleSize * 0.07)), textUnderlineOffset: Math.round(titleSize * 0.16),
        textShadow: `0 4px 30px rgba(0,0,0,0.5), 0 0 ${Math.round(titleSize * 0.4)}px ${glow(0.18 * p)}`,
      }}>{sec.title}</div>
    </div>
  );
};

const mod: AnimModule = {
  kind: 'section',
  description: 'A TITLE or really-important line shown by gaussian-blurring the whole camera and overlaying the text DEAD CENTER, important words highlighted with an accent underline (Akatab, lowercase). Just the title — NO subhead/kicker. The host stays on camera, defocused behind it — never a split. Use for a section header (a new point or chapter) or a line that must land big. Author as {scene:1, anim:section, title, word:cue}. For ambient/running text, use the default caption (over-the-shoulder), not this.',
  category: 'structure',
  tags: ['section', 'title', 'chapter', 'point', 'important', 'headline'],
  scenes: ['host'],
  match: (b) => !!(b as unknown as { section?: unknown }).section,
  render: (c) => <SectionTitle {...c} />,
  priority: 50,
};

export default mod;
