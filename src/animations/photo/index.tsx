// PHOTO — a real photograph shown in the open glide panel while the host stays on the other
// side (avatar ALWAYS on screen). Use it to SHOW a real place/thing the host names: a
// hometown, a building, a landmark. True color (never duotoned — a real place's identity is
// its real look). A slow Ken Burns push keeps it ALWAYS-BUILDING across the beat.
//
// DATA: the plan carries `photo: { img, at, label? }` on a glide beat (authored in the
// diagrams cache: {"scene":2,"anim":"photo","img":"photos/alvastone.png","label":"Alva,
// Oklahoma","word":"hometown"}). `at` is the spoken cue word; the photo LEADS it by POP_LEAD_F.
import React from 'react';
import { Img, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig } from 'remotion';
import type { AnimModule, AnimContext } from '../_contract';
import { glow, GOLD, CREME_DARK } from '../../components/vc/style';
import { SANS } from '../../components/vc/fonts';

const PhotoCard: React.FC<AnimContext> = ({ b, start, end, side }) => {
  const frame = useCurrentFrame();   // 0 at the beat's first frame (the Sequence starts at beat.start)
  const { fps, width, height } = useVideoConfig();
  const portrait = height > width;   // 9:16 short-form: host is full-bleed, so the photo is a
                                     // big card in the LOWER area (face stays visible up top)
  const photo = (b as unknown as { photo?: { img: string; at: number; label?: string } }).photo;
  if (!photo) return null;

  // A photo FILLS the panel, so it is up from the beat's FIRST frame — never a late, voice-led
  // pop that would leave the panel empty at the top of the beat (overlay.from == beat.start;
  // the stage is never empty). It fades/scales in over the first ~0.45s.
  const durF = end - start;
  const p = spring({ frame, fps, config: { damping: 200, stiffness: 200, mass: 0.6 }, durationInFrames: 14 });
  const t = frame / fps;
  // Ken Burns: a slow continuous push from 1.0 across the whole beat, plus a gentle drift —
  // real motion in every third (the build gate) without any wild movement.
  const kb = 1.0 + 0.08 * interpolate(frame, [0, durF], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const drift = Math.sin((t * Math.PI * 2) / 3.4) * 5;
  const panX = side === 'left' ? 60 : 900;   // open half: host glided right → panel left, and vice-versa

  const wrap: React.CSSProperties = portrait
    ? { position: 'absolute', inset: 0, display: 'flex', alignItems: 'flex-end', justifyContent: 'center', paddingBottom: 210 }
    : { position: 'absolute', top: 0, bottom: 0, left: panX, width: 960, display: 'flex', alignItems: 'center', justifyContent: 'center' };
  const cardW = portrait ? 980 : 940;
  const cardH = portrait ? 720 : 620;

  return (
    <div style={wrap}>
      <div style={{
        position: 'relative', width: cardW, height: cardH, borderRadius: 26, overflow: 'hidden',
        opacity: p, transform: `translateY(${(1 - p) * 26 + drift}px) scale(${interpolate(p, [0, 1], [0.96, 1])})`,
        boxShadow: '0 30px 70px rgba(0,0,0,0.55)', border: `1px solid ${glow(0.22)}`,
      }}>
        <Img src={staticFile(photo.img)} style={{ width: '100%', height: '100%', objectFit: 'cover', transform: `scale(${kb})`, transformOrigin: 'center center' }} />
        {/* legibility scrim + caption chip */}
        {photo.label ? (
          <>
            <div style={{ position: 'absolute', left: 0, right: 0, bottom: 0, height: 150, background: 'linear-gradient(0deg, rgba(10,10,12,0.72), rgba(10,10,12,0))' }} />
            <div style={{ position: 'absolute', left: 26, bottom: 22, display: 'flex', alignItems: 'center', gap: 12 }}>
              <div style={{ width: 8, height: 30, borderRadius: 3, background: GOLD.yellow, boxShadow: `0 0 14px ${glow(0.6)}` }} />
              <div style={{ fontFamily: SANS, fontWeight: 800, fontSize: 40, color: CREME_DARK.ink, letterSpacing: '-0.01em' }}>{photo.label}</div>
            </div>
          </>
        ) : null}
      </div>
    </div>
  );
};

const mod: AnimModule = {
  kind: 'photo',
  description: 'A real photograph in the open glide panel while the host stays on camera — use it to SHOW a real place or thing the host names (a hometown, a building, a landmark). True color, slow Ken Burns push. Author as {scene:2 or 3, anim:photo, img:photos/<file>, label:<optional caption>, word:<spoken cue>}.',
  category: 'media',
  tags: ['photo', 'image', 'broll', 'place', 'hometown', 'real'],
  scenes: ['glide'],
  match: (b) => !!(b as unknown as { photo?: unknown }).photo,
  render: (c) => <PhotoCard {...c} />,
  priority: 40,
};

export default mod;
