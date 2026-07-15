import React from 'react';
import { AbsoluteFill, Easing, interpolate, OffthreadVideo, Sequence, staticFile, useCurrentFrame } from 'remotion';
import { Z, ACCENT_RGB } from '../components/vc/style';
import { SANS } from '../components/vc/fonts';
import { CharcoalBg } from '../components/vc/CremeStage';
import { KineticCaption, type KCWord } from '../components/vc/KineticCaption';
import { ANIMATIONS } from '../animations/registry.generated';
import type { AnimScene } from '../animations/_contract';
import { BEATS, TOTAL_FRAMES, SRC, FACE_X, type Beat } from './officialTestBeatPlan';

/**
 * SHORT-FORM (9:16) renderer — the SAME beat plan as the landscape AutoReel, re-laid-out for a
 * 1080×1920 vertical frame. Vertical grammar is different from 16:9: there is NO glide-to-a-
 * side-panel (a portrait frame has no room for it). Instead the host is FULL-BLEED the whole
 * time (the landscape footage cover-cropped and centered on the face), and everything else
 * rides ON TOP as an overlay:
 *   - caption/glide beats  → the word-timed caption as a lower-third (host stays full-bleed)
 *   - section beats        → the section title card (its own portrait layout)
 *   - photo beats          → a big photo card low in the frame (face stays visible up top)
 *   - host/open beats      → just the host, with the one deliberate camera move
 * The plan (timing, which beat carries which device) is identical to the long-form edit, so a
 * video edited once outputs both formats.
 */
const FPS = 30;
const f = (s: number) => Math.round(s * FPS);
const VW = 1080, VH = 1920;
export const AUTO_FRAMES_V = TOTAL_FRAMES;

const BARE_HOST = new Set(['open', 'hostZoom']);
const HOST_PUSH = 0.05;       // gentler push in vertical (the frame is already tight on the face)
const OPEN_SETTLE_S = 0.65;

// Full-bleed host: the 16:9 source scaled to fill the 1080×1920 frame's HEIGHT, then slid
// horizontally so the face (FACE_X, in 1920-landscape terms) sits at frame center. One camera
// move per beat (the open pulls out; every other beat gently pushes in), zooming toward the face.
const PortraitHost: React.FC = () => {
  const frame = useCurrentFrame();
  let bi = 0;
  for (let i = 0; i < BEATS.length; i++) if (frame >= f(BEATS[i].start)) bi = i;
  const b = BEATS[bi];
  const start = b.style === 'open' ? 0 : f(b.start);
  const end = f(b.start + b.dur);
  const local = frame - start;
  const durF = Math.max(end - start, 1);
  let scale = 1;
  if (b.style === 'open') {
    const z = interpolate(local, [0, f(OPEN_SETTLE_S)], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
    scale = interpolate(z, [0, 1], [1.10, 1.0]);
  } else if (BARE_HOST.has(b.style)) {
    const z = interpolate(local, [0, durF], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
    scale = interpolate(z, [0, 1], [1.0, 1.0 + HOST_PUSH]);
  }
  const coverW = Math.round((VH * 16) / 9);      // source is 16:9 → width to fill height 1920
  const faceFrac = FACE_X / 1920;                // face fraction in landscape terms
  const facePx = faceFrac * coverW;              // face x inside the cover-scaled video
  const left = Math.round(VW / 2 - facePx);      // slide so the face is centered
  return (
    <AbsoluteFill style={{ overflow: 'hidden' }}>
      <div style={{ position: 'absolute', left, top: 0, width: coverW, height: VH, transform: `scale(${scale})`, transformOrigin: `${facePx}px ${VH / 2}px` }}>
        <OffthreadVideo src={staticFile(SRC)} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
      </div>
    </AbsoluteFill>
  );
};

const O: React.FC<{ from: number; dur: number; z?: number; children: React.ReactNode }> = ({ from, dur, z = 42, children }) => (
  <Sequence from={from} durationInFrames={Math.max(dur, 1)} layout="none"><AbsoluteFill style={{ zIndex: z }}>{children}</AbsoluteFill></Sequence>
);

// legibility scrim under a lower-third caption (the host's body is busy) + a top scrim for balance
const CaptionScrim: React.FC = () => (
  <AbsoluteFill style={{ background: 'linear-gradient(0deg, rgba(8,8,10,0.82) 0%, rgba(8,8,10,0.5) 22%, rgba(8,8,10,0) 42%)' }} />
);

const capChars = (cap: KCWord[]) => cap.reduce((n, w) => n + w.t.length + 1, 0);
const fitSize = (cap: KCWord[], base: number, min: number, target: number) =>
  Math.max(min, Math.round(base * Math.min(1, Math.sqrt(target / Math.max(capChars(cap), 1)))));

const pick = (b: Beat, scene: AnimScene) => ANIMATIONS.find((a) => a.scenes.includes(scene) && a.match(b));

export const AutoReelVertical: React.FC = () => (
  <AbsoluteFill style={{ fontFamily: SANS, textTransform: 'lowercase', ['--accent-rgb' as string]: ACCENT_RGB } as React.CSSProperties}>
    <AbsoluteFill style={{ zIndex: 0 }}><CharcoalBg /></AbsoluteFill>
    <AbsoluteFill style={{ zIndex: Z.avatar }}><PortraitHost /></AbsoluteFill>
    {BEATS.map((b, i) => {
      const start = f(b.start);
      const end = f(b.start + b.dur);
      const cap = (b.cap || []) as KCWord[];
      // section title card (overlay over the full host)
      const sec = pick(b, 'host');
      if (sec && (b as unknown as { section?: unknown }).section) {
        return <O key={i} from={start} dur={end - start} z={Z.over}>{sec.render({ b, start, end, f, scene: 'host', side: 'left' })}</O>;
      }
      // any glide-scene media (photo card, document panel, …) — its own portrait layout
      const ph = pick(b, 'glide');
      if (ph) {
        return <O key={i} from={start} dur={end - start} z={Z.over}>{ph.render({ b, start, end, f, scene: 'glide', side: 'left' })}</O>;
      }
      // a TEXT beat (landscape keeps the host full-frame with over-the-shoulder text; in
      // vertical it is a lower-third over the full-bleed host) — never a split
      if ((b.style === 'glideR' || b.style === 'glideL') && cap.length) {
        return (
          <O key={i} from={start} dur={end - start} z={Z.over}>
            <CaptionScrim />
            <KineticCaption words={cap} from={b.start} size={fitSize(cap, 70, 52, 260)} dark side="center" yAlign="bottom" emph="glow" leadF={5} />
          </O>
        );
      }
      return null; // host / open: just the host on camera
    })}
  </AbsoluteFill>
);
