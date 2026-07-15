import React from 'react';
import { AbsoluteFill, Easing, OffthreadVideo, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig } from 'remotion';
import { ENGINE } from '../../engine.config';
import { SPLIT_HOST_W } from './style';

/**
 * AvatarGlide — the host in a PORTRAIT liquid-glass panel that GLIDES at ORIGINAL
 * SIZE. The avatar never scales during a glide: it stays full-resolution and
 * TRANSLATES (a horizontal pan) into a portrait glass on the left or right, so it
 * reads as a smooth momentum slide — no zoom in/out, never leaving the screen, and
 * glides straight back to the full-frame hero. The OPEN area it vacates is for
 * content (filled by the composition, NOT inside this glass). The only scale move
 * allowed is an opening hero zoom (e.g. a slow zoom-OUT), via span.zoom.
 */
// glideL/glideR = the portrait liquid-glass panel (rounded, floating over the open half).
// docL/docR    = a hard-edged, FULL-HEIGHT camera slice flush to the frame edge (NO glass, NO
//                rounded corners, NO background gap) — the host half of a document split-screen,
//                the article full-bleed on the other side. See SPLIT_HOST_W in style.ts.
export type GlideState = 'hero' | 'glideL' | 'glideR' | 'docL' | 'docR' | 'absent';
// zoomEase: 'out' (default) front-loads the push (settles early); 'inOut' is a steady
// slow push that keeps moving the whole span; 'linear' is constant speed.
export type GlideSpan = { start: number; state: GlideState; zoom?: [number, number]; zoomFrac?: number; zoomEase?: 'out' | 'linear' | 'inOut' };

const GW = 620;   // portrait glass width
const GH = 1000;  // portrait glass height
const GY = 40;    // top margin
const GM = 56;    // side margin
const FACE_X = ENGINE.avatar.faceX; // DEFAULT host face x — derives from engine.config; override per-call via the faceX prop
// Vertical offset MUST keep the 1080-tall video covering the GH-tall panel (no
// black bar at top/bottom): valid range is [GH-1080, 0] = [-80, 0]. -60 fills the
// panel and gives the head modest headroom.
const INNER_TY = -60;

type Geo = { left: number; width: number; top: number; height: number; radius: number; glass: number; tx: number; ty: number; opacity: number };

const geoOf = (s: GlideState, faceX: number): Geo => {
  const glideTx = GW / 2 - faceX;            // center the face in the 620-wide glass window
  const docTx = SPLIT_HOST_W / 2 - faceX;    // center the face in the full-height split slice
  if (s === 'glideL') return { left: GM, width: GW, top: GY, height: GH, radius: 32, glass: 1, tx: glideTx, ty: INNER_TY, opacity: 1 };
  if (s === 'glideR') return { left: 1920 - GW - GM, width: GW, top: GY, height: GH, radius: 32, glass: 1, tx: glideTx, ty: INNER_TY, opacity: 1 };
  // Document split: full-height (1080), flush to the frame edge, no glass, no rounding, ty 0
  // (the whole frame height shows — no headroom crop). The article fills the rest full-bleed.
  if (s === 'docL') return { left: 0, width: SPLIT_HOST_W, top: 0, height: 1080, radius: 0, glass: 0, tx: docTx, ty: 0, opacity: 1 };
  if (s === 'docR') return { left: 1920 - SPLIT_HOST_W, width: SPLIT_HOST_W, top: 0, height: 1080, radius: 0, glass: 0, tx: docTx, ty: 0, opacity: 1 };
  if (s === 'absent') return { left: 0, width: 1920, top: 0, height: 1080, radius: 0, glass: 0, tx: 0, ty: 0, opacity: 0 };
  return { left: 0, width: 1920, top: 0, height: 1080, radius: 0, glass: 0, tx: 0, ty: 0, opacity: 1 }; // hero = full-frame (unchanged)
};

const resolve = (src: string) => (/^(https?:|\/)/.test(src) ? src : staticFile(src));
const T = 26;

export const AvatarGlide: React.FC<{ src: string; spans: GlideSpan[]; faceX?: number; transparent?: boolean }> = ({ src, spans, faceX = FACE_X, transparent = false }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  let idx = 0;
  for (let i = 0; i < spans.length; i++) if (frame >= spans[i].start) idx = i;
  const span = spans[idx];
  const prev = spans[idx - 1];
  const nextStart = spans[idx + 1]?.start ?? durationInFrames;
  const local = frame - span.start;

  const raw = spring({ frame: local, fps, config: { damping: 200, stiffness: 120, mass: 0.9 }, durationInFrames: T });
  const t = local >= T + 2 ? 1 : raw;
  const A = geoOf(prev ? prev.state : span.state, faceX);
  let B = geoOf(span.state, faceX);
  // going ABSENT from a glide: fade out IN PLACE — keep the previous geometry so the
  // avatar doesn't un-glide/slide as it disappears (that slide reads as a jerk).
  if (span.state === 'absent' && prev && prev.state !== 'absent') B = { ...A, opacity: 0 };
  const lerp = (a: number, b: number) => interpolate(t, [0, 1], [a, b]);

  const left = lerp(A.left, B.left);
  const width = lerp(A.width, B.width);
  const top = lerp(A.top, B.top);
  const height = lerp(A.height, B.height);
  const radius = lerp(A.radius, B.radius);
  const glass = lerp(A.glass, B.glass);
  const tx = lerp(A.tx, B.tx);
  const ty = lerp(A.ty, B.ty);

  let opacity = 1;
  if (span.state === 'absent') opacity = lerp(prev && prev.state === 'absent' ? 0 : 1, 0);
  else if (prev && prev.state === 'absent') opacity = lerp(0, 1);

  // Inner zoom (hero only; glides never carry their own zoom).
  const zoomEase = (s?: GlideSpan) => (s?.zoomEase === 'linear' ? Easing.linear : s?.zoomEase === 'inOut' ? Easing.inOut(Easing.cubic) : Easing.out(Easing.cubic));
  let scale = 1;
  if (span.zoom) {
    const frac = span.zoomFrac ?? 1;
    const zf = Math.max((nextStart - span.start) * frac, 1);
    const z = interpolate(local, [0, zf], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: zoomEase(span) });
    scale = interpolate(z, [0, 1], span.zoom);
  }
  // Anti-STUTTER (Ryan 2026-06-28): a zoomed hero gliding to a side panel would POP its
  // inner scale (e.g. 1.06→1.0) in one frame at the seam, while the geometry slides
  // smoothly. Carry the PREVIOUS span's ending scale and ease the LEFTOVER out with the
  // transition `t`, so the un-zoom glides in sync with the slide. The term is the seam
  // DISCONTINUITY only (prevScale − this span's start scale): for an entrance zoom the two
  // are equal → 0 → the zoom still starts immediately (no dampening).
  const curScaleAtStart = span.zoom ? span.zoom[0] : 1;
  let prevScale = curScaleAtStart; // no prev → no smoothing
  if (prev) {
    prevScale = 1;
    if (prev.zoom) {
      const pzf = Math.max((span.start - prev.start) * (prev.zoomFrac ?? 1), 1);
      const pz = interpolate(span.start - prev.start, [0, pzf], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: zoomEase(prev) });
      prevScale = interpolate(pz, [0, 1], prev.zoom);
    }
  }
  scale = scale + (prevScale - curScaleAtStart) * (1 - t);

  return (
    <AbsoluteFill>
      <div
        style={{
          position: 'absolute',
          left, top, width, height,
          borderRadius: radius,
          overflow: 'hidden',
          opacity,
          boxShadow: glass > 0.05 ? '0 34px 90px rgba(0,0,0,0.55)' : undefined,
          border: glass > 0.05 ? `1px solid rgba(255,255,255,${0.16 * glass})` : undefined,
        }}
      >
        <div style={{ position: 'absolute', left: 0, top: 0, width: 1920, height: 1080, transform: `translate(${tx}px, ${ty}px) scale(${scale})`, transformOrigin: 'center center' }}>
          <OffthreadVideo src={resolve(src)} transparent={transparent} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
        </div>
        {glass > 0.05 ? (
          <>
            <div style={{ position: 'absolute', inset: 0, borderRadius: radius, background: `linear-gradient(135deg, rgba(255,255,255,${0.16 * glass}), rgba(255,255,255,0) 44%)`, pointerEvents: 'none' }} />
            <div style={{ position: 'absolute', inset: 0, borderRadius: radius, boxShadow: `inset 0 1px 0 rgba(255,255,255,${0.3 * glass})`, pointerEvents: 'none' }} />
          </>
        ) : null}
      </div>
    </AbsoluteFill>
  );
};
