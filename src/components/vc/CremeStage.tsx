import React from 'react';
import { AbsoluteFill } from 'remotion';

/**
 * CharcoalBg — the engine's ONE constant background (Ryan 2026-06-28, locked with the
 * charcoal + yellow-glow brand). Charcoal grey base + a radial fade + a fine, dense,
 * even soft-white square grid (~12px cells). Two contrast levels, same spatial rhythm
 * so the choice is contrast, not layout:
 *   A — subtle/premium: grid felt-not-seen (Linear/Vercel restraint), no major grid.
 *   B — blueprint:      crisper minor grid + a 60px MAJOR grid for graph-paper structure.
 * Grid is drawn in screen space (backgroundSize) so it scales 1:1 with a ZoomPan camera
 * as one coherent layer — no independent crawl. 1px hairlines (never sub-pixel) + low
 * alpha keep it shimmer-free under h.264. Pair with the CREME_DARK content palette.
 */
export type CharcoalVariant = 'A' | 'B';
const CHARCOAL: Record<CharcoalVariant, { radial: string; cell: number; line: string; lineW: number; gridOpacity: number; major: { cell: number; line: string; lineW: number } | null; vignette: string }> = {
  A: {
    radial: 'radial-gradient(130% 110% at 50% 0%, #24272D 0%, #1A1C21 55%, #131419 100%)',
    cell: 12, line: 'rgba(245,243,238,0.05)', lineW: 1, gridOpacity: 0.9, major: null,
    vignette: 'radial-gradient(120% 90% at 50% 40%, transparent 55%, rgba(0,0,0,0.36))',
  },
  B: {
    radial: 'radial-gradient(130% 110% at 50% 0%, #25282E 0%, #1B1D22 48%, #141518 100%)',
    cell: 12, line: 'rgba(245,243,238,0.07)', lineW: 1, gridOpacity: 1,
    major: { cell: 60, line: 'rgba(245,243,238,0.10)', lineW: 1 },
    vignette: 'radial-gradient(120% 95% at 50% 38%, transparent 50%, rgba(6,6,8,0.46))',
  },
};
const gridCss = (line: string, w: number) => `linear-gradient(${line} ${w}px, transparent ${w}px), linear-gradient(90deg, ${line} ${w}px, transparent ${w}px)`;
export const CharcoalBg: React.FC<{ variant?: CharcoalVariant }> = ({ variant = 'A' }) => {
  const c = CHARCOAL[variant];
  return (
    <AbsoluteFill style={{ background: c.radial }}>
      <AbsoluteFill style={{ backgroundImage: gridCss(c.line, c.lineW), backgroundSize: `${c.cell}px ${c.cell}px`, opacity: c.gridOpacity }} />
      {c.major ? (
        <AbsoluteFill style={{ backgroundImage: gridCss(c.major.line, c.major.lineW), backgroundSize: `${c.major.cell}px ${c.major.cell}px` }} />
      ) : null}
      <AbsoluteFill style={{ background: c.vignette, pointerEvents: 'none' }} />
    </AbsoluteFill>
  );
};
