import React from 'react';
import { AbsoluteFill, Img, staticFile, useCurrentFrame, useVideoConfig } from 'remotion';

/**
 * FlowerBg — the `bloomers` channel background: a flowerLESS base image with individual flower
 * SPRITES scattered on top, EACH shaking slightly on its own (Matthew chose true per-flower
 * motion, 2026-07-13). It's what shows behind the green-screen-keyed host, so the host composites
 * onto a living watercolor field instead of the charcoal grid.
 *
 * DATA-DRIVEN so it adapts to whatever sprites Matthew exports — no layout baked in:
 *   bg       staticFile path to the flowerless background image (fills the frame, cover)
 *   flowers  one entry per sprite: { img, x, y, size, rot?, speed?, sway? }
 *              x,y   = center position as 0..100 % of the frame (so it's resolution-independent)
 *              size  = width as % of frame width
 *              rot   = base rotation (deg); speed/sway scale this flower's shake (defaults vary
 *                      per-index so nothing moves in lock-step)
 * Each flower rocks with a gentle sine on rotation + a hair of drift, at its own phase — a light
 * "breeze," never a spin. Works in both 16:9 and 9:16 (percentages).
 */
export type FlowerSpec = { img: string; x: number; y: number; size: number; rot?: number; speed?: number; sway?: number };

const Flower: React.FC<{ spec: FlowerSpec; i: number }> = ({ spec, i }) => {
  const frame = useCurrentFrame();
  const { fps, width } = useVideoConfig();
  const t = frame / fps;
  // per-flower phase + speed so the field never pulses in unison
  const phase = i * 1.7;
  const speed = spec.speed ?? (0.7 + (i % 5) * 0.06);      // rad/s-ish, gentle
  const swayDeg = spec.sway ?? (3 + (i % 4));               // ±degrees of rock
  const rock = Math.sin(t * speed * Math.PI + phase) * swayDeg;
  const bob = Math.cos(t * speed * Math.PI * 0.9 + phase) * 0.4;  // tiny vertical drift (%)
  const w = spec.size;
  return (
    <div style={{
      position: 'absolute', left: `${spec.x}%`, top: `${spec.y + bob}%`, width: `${w}%`,
      transform: `translate(-50%, -50%) rotate(${(spec.rot ?? 0) + rock}deg)`,
      transformOrigin: 'center 60%',   // pivot low, like a stem — reads as a sway, not a spin
    }}>
      <Img src={staticFile(spec.img)} style={{ width: '100%', height: 'auto', display: 'block' }} />
    </div>
  );
};

export const FlowerBg: React.FC<{ bg: string; flowers: FlowerSpec[] }> = ({ bg, flowers }) => (
  <AbsoluteFill>
    <Img src={staticFile(bg)} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
    {flowers.map((spec, i) => <Flower key={i} spec={spec} i={i} />)}
  </AbsoluteFill>
);
