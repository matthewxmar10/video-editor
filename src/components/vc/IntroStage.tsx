import React from 'react';
import { AbsoluteFill, Img, OffthreadVideo, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig } from 'remotion';
import { ZoomPan, type CamStop } from './ZoomPan';
import { sec, GOLD, CREME_DARK } from './style';
import { SANS } from './fonts';
import { type KCWord } from './KineticCaption';

/**
 * IntroStage — THE INTRO ASSET (Ryan 2026-07-01: "those first five to ten seconds are so
 * important… we have to earn every second"). One continuous camera story over SB1, every
 * move anchored to a spoken word — the camera never parks on something that already landed:
 *
 *   1. Opens TIGHT on the host's face (~1.5x), then zooms OUT along a DIAGONAL — the host
 *      settles right-of-frame and the left side opens up. The settle completes just before
 *      the first money word is spoken.
 *   2. The POWER PHRASE ("high retention edit") stacks into that opened left space, each
 *      word popping on its exact spoken frame (emphasis word bigger + glowing yellow).
 *   3. On the first NAME-DROP, a quick WHIP-PAN RIGHT slides the host (and the phrase) out
 *      of frame and reveals the LOGO ZONE on the charcoal grid: each OFFICIAL logo pops on
 *      its spoken word, then a slow push carries the shot to the beat's end.
 *
 * Camera stops are DERIVED from the word times (settle = first phrase word − 6f; whip lands
 * = first logo word − 4f), so the asset re-times itself to any script. The video copy here
 * is MUTED — the base avatar layer underneath carries the audio. Deterministic throughout.
 */
export type IntroLogo = { img: string; label?: string; at: number; w?: number; tile?: boolean; glow?: string };
// tile: true = an opaque app-icon square (gets rounded corners + a drop shadow);
// false = a transparent BARE MARK (icon only, no wordmark) floating on the footage with a
//         gentle brand-colored glow (`glow`, an rgba color) — Ryan 2026-07-01: icons, not words.

// Visual pops LEAD the voice: a spring needs ~5 frames to read, so it starts this many frames
// BEFORE the word's timestamp — the element is fully on screen the instant the word is voiced.
const POP_LEAD_F = 5;

const resolve = (src: string) => (/^(https?:|\/)/.test(src) ? src : staticFile(src));

export const IntroStage: React.FC<{
  src: string;                 // the host cut (same file the avatar layer plays), muted here
  from: number;                // beat start (seconds)
  durFrames: number;
  faceX?: number;              // host face x in the 1920 frame (the tight-open anchor)
  phrase?: KCWord[];           // money words, absolute seconds
  logos?: IntroLogo[];         // official logo pops, absolute seconds
}> = ({ src, from, durFrames, faceX = 960, phrase = [], logos = [] }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const f = (t: number) => Math.round((t - from) * fps);

  // ── HARD RULE (Ryan 2026-07-01): the camera NEVER leaves the avatar's 1920×1080 canvas —
  // no background grid may show during a host-owned beat. Every stop is CLAMPED so the view
  // window is mathematically inside the video plane: structural, not a convention.
  const cs = (s: number, x: number, y: number, fr: number): CamStop => {
    // the ±6px safety margin only applies when zoomed IN — at scale 1.0 the view
    // window equals the plane, the margins invert the bounds, and the "natural"
    // stop lands at (966, 546): a 6px offset blip at the boundary cut (found by
    // pixel-diff vs the raw footage, 2026-07-03)
    const m = s > 1.001 ? 6 : 0;
    return {
      f: fr,
      scale: s,
      x: Math.max(960 / s + m, Math.min(1920 - 960 / s - m, x)),
      y: Math.max(540 / s + m, Math.min(1080 - 540 / s - m, y)),
    };
  };

  // ── camera choreography, derived from the spoken words — all WITHIN the frame ────────
  const settleF = Math.max(20, phrase.length ? f(phrase[0].at) - 6 : 30);          // zoom-out lands just before word 1
  const panStartF = logos.length ? Math.max(settleF + 10, f(logos[0].at) - 16) : durFrames;
  const panLandF = logos.length ? Math.max(panStartF + 8, f(logos[0].at) - 4) : durFrames;
  // the frame the camera starts drifting home (boundary-velocity law). The logo fade is
  // DECOUPLED from this drift (Ryan 2026-07-03: the runway cap made the drift start
  // before the last name-drop, so the Remotion mark popped into a half-done fade and
  // never hit full brightness) — logos keep their own clock and exit just before the cut.
  const homeF = logos.length
    ? Math.max(panLandF + 4, Math.min(f(logos[logos.length - 1].at), durFrames - 45))
    : Math.round(durFrames * 0.7);
  // INTRO CAMERA (Ryan 2026-07-04): larger crop on the face → zoom OUT while panning
  // LEFT to the boxed words (HORIZONTAL only, y stays centered — never down) → settle to
  // the FULL natural uncropped frame before the cut, so the glide that follows starts
  // from the exact same framing (no size jump = smooth glide). No vertical drift anywhere.
  const stops: CamStop[] = [
    cs(1.32, faceX, 540, 0),                                   // larger crop, tight on the face — centered
    cs(1.1, 838, 540, settleF),                                // zoom out + pan LEFT to the boxed words
    ...(logos.length
      ? [
          cs(1.1, 838, 540, panStartF),                        // hold while the phrase lands
          cs(1.1, 1082, 540, panLandF),                        // pan RIGHT to the logo zone (same zoom)
          cs(1.1, 1082, 540, homeF),                           // hold on the logos (>=1.5s runway)
          cs(1.0, 960, 540, durFrames - 2),                    // settle to the natural uncropped frame
        ]
      // no name-drop logos: hold the pan-left phrase frame, then settle to the natural
      // uncropped frame — the glide after the cut starts from the SAME framing (smooth).
      : [cs(1.1, 838, 540, Math.max(settleF + 8, durFrames - 45)),
         cs(1.0, 960, 540, durFrames - 2)]),
  ];
  // the phrase HANDS OFF during the whip (fades as the camera leaves it for the logos);
  // with NO logos to hand off to, it holds full-bright and takes the same quick exit
  // clock as the logo marks — gone 4f before the cut so the boundary frame stays clean
  const phraseOpacity = logos.length
    ? interpolate(frame, [panStartF, panLandF], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' })
    : interpolate(frame, [durFrames - 12, durFrames - 4], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  return (
    <AbsoluteFill>
      <ZoomPan stops={stops}>
        {/* the host plane (canvas 0..1920) — MUTED; the hidden base layer owns the audio */}
        <div style={{ position: 'absolute', left: 0, top: 0, width: 1920, height: 1080 }}>
          <OffthreadVideo muted src={resolve(src)} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
        </div>
        {/* POWER PHRASE — the locked stack (Ryan 2026-07-03 spec): power words ONE PER
            LINE, ALL CAPS, smaller type; hyphenated compounds split into their own lines
            ("high-retention" → HIGH / RETENTION). A box line DRAWS around the stack and
            COMPLETES the instant the last power word ("EDIT") is voiced — the same
            voice-led clock as every pop. Hands off (fades) during the whip. */}
        {/* column centers sit EVEN on both sides (Ryan): text ≈ −430px from frame center at
            the settle, logos ≈ +430px at the whip — the shot reads balanced, not lopsided */}
        {(() => {
          const lines = phrase.flatMap((w) =>
            w.t.split('-').filter(Boolean).map((part, j) => ({ t: part, atF: f(w.at) + j * 8, big: !!w.big })));
          if (!lines.length) return null;
          const boxP = interpolate(frame,
            [f(phrase[0].at) - POP_LEAD_F, f(phrase[phrase.length - 1].at)], [0, 1],
            { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
          return (
            <div style={{ position: 'absolute', left: 205, top: 330, display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 8, padding: '26px 34px', opacity: phraseOpacity }}>
              {boxP > 0 && (
                <svg style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', overflow: 'visible' }}>
                  <rect x={1.5} y={1.5} width="calc(100% - 3px)" height="calc(100% - 3px)" rx={18} fill="none" stroke={GOLD.yellow} strokeWidth={3} pathLength={100} strokeDasharray={100} strokeDashoffset={100 * (1 - boxP)} strokeLinecap="round" style={{ filter: 'drop-shadow(0 0 10px rgba(var(--accent-rgb,247,199,21),0.55))' }} />
                </svg>
              )}
              {lines.map((w, i) => {
                const p = spring({ frame: frame - (w.atF - POP_LEAD_F), fps, config: { damping: 200, stiffness: 240, mass: 0.5 }, durationInFrames: 8 });
                return (
                  <div
                    key={i}
                    style={{
                      fontFamily: SANS, fontWeight: 800, fontSize: w.big ? 62 : 54, lineHeight: 1.0,
                      textTransform: 'uppercase',
                      color: w.big ? GOLD.yellow : CREME_DARK.ink, letterSpacing: '0.02em',
                      textShadow: w.big
                        ? '0 0 46px rgba(var(--accent-rgb,247,199,21),0.55), 0 2px 26px rgba(0,0,0,0.7)'
                        : '0 2px 26px rgba(0,0,0,0.7)',
                      opacity: p, transform: `translateY(${(1 - p) * 14}px) scale(${interpolate(p, [0, 1], [0.8, 1])})`,
                    }}
                  >{w.t}</div>
                );
              })}
            </div>
          );
        })()}
        {/* LOGO ZONE — a stacked column over the RIGHT side of the footage (never off the
            avatar canvas), each official mark popping on its spoken word with a gentle
            counter-phase float. Transparent wordmarks ride a dark liquid-glass chip so they
            stay legible over the room. */}
        {logos.map((lg, i) => {
          const p = spring({ frame: frame - (f(lg.at) - POP_LEAD_F), fps, config: { damping: 200, stiffness: 200, mass: 0.6 }, durationInFrames: 12 });
          // full-bright until the last ~0.27s, then a snappy exit completing 4f before the
          // cut — the boundary frame stays logo-free (camera stops untouched, no blip).
          // Ceiling note: the last name-drop's word time bounds the mark's life; a script
          // whose name-drop lands earlier buys the logo more air for free.
          const fade = interpolate(frame, [durFrames - 12, durFrames - 4], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
          const bob = Math.sin(((frame / fps) * Math.PI * 2) / 2.8 + i * 2.1) * 5;
          const w = lg.w ?? 240;
          const y = 400 + i * 300;
          const glow = lg.glow ?? 'rgba(247,199,21,0.5)';
          return (
            <div
              key={i}
              style={{
                position: 'absolute', left: 1445 - w / 2, top: y + bob, transform: `translateY(-50%) scale(${interpolate(p, [0, 1], [0.7, 1])})`,
                opacity: fade * (p), display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 20,
              }}
            >
              {lg.tile ? (
                <Img src={resolve(lg.img)} style={{ width: w, height: 'auto', borderRadius: 28, boxShadow: '0 24px 60px rgba(0,0,0,0.55), 0 0 40px rgba(var(--accent-rgb,247,199,21),0.12)' }} />
              ) : (
                // BARE MARK — the icon floats on the footage with a gentle brand glow
                <Img src={resolve(lg.img)} style={{ width: w, height: 'auto', display: 'block', filter: `drop-shadow(0 0 26px ${glow}) drop-shadow(0 0 70px ${glow}) drop-shadow(0 10px 30px rgba(0,0,0,0.45))` }} />
              )}
              {lg.label ? (
                <div style={{ fontFamily: SANS, fontWeight: 800, fontSize: 36, color: CREME_DARK.ink, letterSpacing: '-0.01em', textShadow: '0 2px 20px rgba(0,0,0,0.7)' }}>{lg.label}</div>
              ) : null}
            </div>
          );
        })}
      </ZoomPan>
    </AbsoluteFill>
  );
};
