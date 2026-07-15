// Look tokens for the CS2 stream badges (Twitch / Subscribe / Discord).
// These are STANDALONE overlay clips (transparent-bg ProRes), not beat-driven
// animation packs — so they live under the channel, not src/animations/.
export const BADGE = {
  fps: 30,
  W: 1920,
  H: 1080,
  D: 120, // 4.0s — self-contained in -> hold -> out
} as const;

export const COLORS = {
  twitch: '#9146ff',
  yt: '#ff0033',
  discord: '#5865f2',
  glass: 'rgba(17,20,27,0.82)',
  border: 'rgba(255,255,255,0.10)',
  ink: '#f5f6fa',
} as const;

// A layered accent glow (soft bloom) for icons + weapons.
export const glow = (hex: string) =>
  `drop-shadow(0 0 12px ${hex}) drop-shadow(0 0 30px ${hex}aa) drop-shadow(0 10px 20px rgba(0,0,0,0.55))`;
