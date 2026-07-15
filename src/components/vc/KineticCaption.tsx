import React from 'react';
import { interpolate, spring, useCurrentFrame, useVideoConfig } from 'remotion';
import { sec, CREME, CREME_DARK, GOLD } from './style';
import { SANS } from './fonts';

export type KCWord = { t: string; at: number; big?: boolean };

/**
 * KineticCaption — the VO words appear ONE-BY-ONE on their real whisperX timestamp
 * (each word pops exactly as the host says it), accumulating into a wrapping caption.
 * All text is AKATAB, lowercase; emphasized words (`big`) are HIGHLIGHTED WITH AN ACCENT
 * UNDERLINE (never a glow or a second face). `from` = the beat's start time (seconds).
 * `side` places the block: 'osL'/'osR' = an over-the-shoulder block in the upper-left/right
 * (Matthew's ambient text mode — over the full-frame host, opposite the face); 'left'/'right'
 * = the open half beside a glided avatar; 'center' = full-frame takeover. Rows sit tight.
 */
export const KineticCaption: React.FC<{ words: KCWord[]; from: number; size?: number; maxWidth?: number; dark?: boolean; side?: 'left' | 'right' | 'center' | 'osL' | 'osR'; yAlign?: 'center' | 'bottom' | 'top'; emph?: 'glow'; leadF?: number }> = ({ words, from, size = 58, maxWidth = 1440, dark = false, side = 'center', yAlign = 'center', leadF = 0 }) => {
  const frame = useCurrentFrame(); const { fps } = useVideoConfig();
  const f = sec;
  // On charcoal the near-black ink goes invisible — flip normal words to a light token
  // and brighten coral so emphasis still pops (CREME_DARK; see CharcoalBg).
  const ink = dark ? CREME_DARK.ink : CREME.ink;
  const accent = dark ? GOLD.yellow : CREME.coral; // the underline (highlight) color
  // 'osL'/'osR' — OVER-THE-SHOULDER: a compact block up in a top corner over the full-frame
  // host, on the side away from the face, so it never covers the face and reads as "on the
  // background." A soft text shadow keeps it legible over live footage (no card/backdrop).
  const overShoulder = side === 'osL' || side === 'osR';
  const box: React.CSSProperties = side === 'osL'
    ? { position: 'absolute', top: 150, left: 96, width: 780, display: 'flex', alignItems: 'flex-start', justifyContent: 'flex-start' }
    : side === 'osR'
    ? { position: 'absolute', top: 150, right: 96, width: 780, display: 'flex', alignItems: 'flex-start', justifyContent: 'flex-start' }
    : side === 'left'
    ? { position: 'absolute', top: 0, bottom: 0, left: 50, width: 1140, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '0 30px' }
    : side === 'right'
    ? { position: 'absolute', top: 0, bottom: 0, right: 50, width: 1140, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '0 30px' }
    : { position: 'absolute', inset: 0, display: 'flex', justifyContent: 'center', alignItems: 'center', padding: '0 110px' };
  // yAlign 'bottom' anchors the caption block as a lower-third (text-over-avatar style)
  // instead of vertically centering it — used for full-frame host beats so the face stays
  // hero and the caption rides low. paddingBottom 300 keeps it ~20% UP off the bottom/mic
  // (Ryan 2026-06-30: "move it 20% off the mic"). Backward-compatible: default 'center'.
  if (yAlign === 'bottom') { box.alignItems = 'flex-end'; box.paddingBottom = 300; }
  // yAlign 'top' rides the caption as a TOP strip (e.g. a deck lead-in line above the card row).
  if (yAlign === 'top') { box.alignItems = 'flex-start'; box.paddingTop = 110; }
  const innerMax = overShoulder ? 760 : side === 'center' ? maxWidth : Math.min(maxWidth, 1060);
  // ALWAYS-BUILDING: after words land the block keeps living — a slow counter-phase
  // float (the same idle grammar as every asset; a landed caption must never be a
  // still — the build gate failed caption tails on flub-2, 2026-07-04)
  const drift = Math.sin(((frame / fps) * Math.PI * 2) / 2.8) * 4;
  return (
    <div style={box}>
      {/* tight, left-set typography (Ryan 2026-06-30: "no more centered justified" —
          ragged-right reads tighter and more natural than centered wrapped lines) */}
      <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: overShoulder ? 'flex-start' : 'flex-start', alignItems: 'baseline', columnGap: Math.round(size * 0.2), rowGap: Math.round(size * 0.16), maxWidth: innerMax, lineHeight: 1.08, textTransform: 'lowercase', transform: `translateY(${drift}px)` }}>
        {words.map((w, i) => {
          // leadF: pops start this many frames BEFORE the word (the POP_LEAD law — a spring
          // needs ~5f to read; the word should be fully visible the instant it's voiced).
          const local = f(w.at) - f(from) - leadF;
          // Render ALL words from frame 0 (space reserved) so a new word NEVER reflows /
          // pushes earlier words left — each appears in its FINAL position, in place.
          const p = spring({ frame: frame - local, fps, config: { damping: 200, stiffness: 240, mass: 0.5 }, durationInFrames: 8 });
          // EMPHASIS = an accent UNDERLINE (Matthew, 2026-07-13): important words are the same
          // face + size, just HIGHLIGHTED with a thick accent underline — never a glow, never a
          // second face. Over-the-shoulder text carries a soft shadow so it stays legible over
          // live footage without any card/backdrop behind it.
          const shadow = overShoulder ? { textShadow: '0 2px 18px rgba(0,0,0,0.85), 0 0 2px rgba(0,0,0,0.9)' } : {};
          const underline: React.CSSProperties = w.big
            ? { textDecorationLine: 'underline', textDecorationColor: accent, textDecorationThickness: Math.max(3, Math.round(size * 0.08)), textUnderlineOffset: Math.round(size * 0.16) }
            : {};
          const wStyle: React.CSSProperties = { fontFamily: SANS, fontStyle: 'normal', fontWeight: 800, fontSize: size, color: ink, letterSpacing: '-0.01em', ...shadow, ...underline };
          return (
            <span key={i} style={{
              ...wStyle,
              opacity: p, transform: `translateY(${(1 - p) * 10}px) scale(${interpolate(p, [0, 1], [0.72, 1])})`,
              display: 'inline-block',
            }}>{w.t}</span>
          );
        })}
      </div>
    </div>
  );
};
