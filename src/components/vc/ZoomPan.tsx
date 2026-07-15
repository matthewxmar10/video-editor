import React from 'react';
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from 'remotion';
import { CANVAS } from './style';

/**
 * STYLE 7 — ZoomPan. One continuous camera move over a STATIC scene: zoom into a
 * point of interest, pan to the next, ... then zoom back out — no cut. Drives a
 * scale+translate on the children so the focused point (x,y in the 1920x1080 scene)
 * sits at screen center. Works for any N points (the script decides how many).
 *
 * stops = camera keyframes by LOCAL frame: { f, scale, x, y }. Put two stops with the
 * same value a few frames apart to HOLD on a point (a natural "look", not a constant
 * glide). Eased per-segment so it accelerates/decelerates like a real camera.
 */
export type CamStop = { f: number; scale: number; x: number; y: number };

const seg = (frame: number, stops: CamStop[], key: 'scale' | 'x' | 'y') => {
  for (let i = 0; i < stops.length - 1; i++) {
    const a = stops[i], b = stops[i + 1];
    if (frame <= b.f || i === stops.length - 2) {
      return interpolate(frame, [a.f, b.f], [a[key], b[key]], {
        extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.inOut(Easing.cubic),
      });
    }
  }
  return stops[stops.length - 1][key];
};

export const ZoomPan: React.FC<{ stops: CamStop[]; children: React.ReactNode }> = ({ stops, children }) => {
  const frame = useCurrentFrame();
  const s = seg(frame, stops, 'scale');
  const px = seg(frame, stops, 'x');
  const py = seg(frame, stops, 'y');
  const tx = CANVAS.w / 2 - px * s;
  const ty = CANVAS.h / 2 - py * s;
  return (
    <AbsoluteFill style={{ transform: `translate(${tx}px, ${ty}px) scale(${s})`, transformOrigin: '0 0' }}>
      {children}
    </AbsoluteFill>
  );
};
