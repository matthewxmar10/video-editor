import React from 'react';
import { AbsoluteFill, Sequence } from 'remotion';
import { Z, ACCENT_RGB } from '../components/vc/style';
import { SANS } from '../components/vc/fonts';
import { AvatarGlide, type GlideSpan } from '../components/vc/AvatarGlide';
import { CharcoalBg } from '../components/vc/CremeStage';
import { FlowerBg } from '../components/vc/FlowerBg';
import { KineticCaption, type KCWord } from '../components/vc/KineticCaption';
import { IntroStage, type IntroLogo } from '../components/vc/IntroStage';
import { LOGO_IMG } from '../animations/_shared';
import { ANIMATIONS } from '../animations/registry.generated';
import type { AnimScene } from '../animations/_contract';
import { BEATS, TOTAL_FRAMES, SRC, FACE_X, GREENSCREEN, type Beat } from './officialTestBeatPlan';

/**
 * DETERMINISTIC renderer — "beat and GLIDE". It makes no editing decisions; it renders the
 * beat plan scripts/build_matched_plan.py computed from the word-timings (same words ->
 * same plan -> same edit). The host rides the CANONICAL grammar (AvatarGlide): a glide is a
 * real spring-interpolated momentum SLIDE into a portrait liquid-glass panel, and every hero
 * beat carries a continuous push-in zoom (never a frozen frame). Text is rationed to
 * meaningful beats; structural moments become a motion diagram / zoom-pan tour. Graphics
 * appear when their content starts, with the host full-frame underneath the opaque graphic,
 * so there is NEVER an empty grid frame.
 *
 * ANIMATIONS ARE PLUGINS. This file owns only the BASE spine: the charcoal bg, the host
 * (AvatarGlide) + camera, the intro, and the word-timed caption fallback. Every diagram is a
 * self-contained module discovered from src/animations/ via the generated registry — this
 * renderer never names one. A glide beat renders the matching animation, else the caption; a
 * host beat renders the matching overlay, else nothing (host on camera). Drop/remove an
 * animation folder + regenerate = the render changes, with zero edits here.
 */
const FPS = 30;
const f = (s: number) => Math.round(s * FPS);
// SRC / FACE_X come from the generated plan (per-video), so this renderer is generic —
// a new video needs NO edit here; the plan carries its source and face-anchor.
export const AUTO_FRAMES = TOTAL_FRAMES;

const BARE_HOST = new Set(['open', 'hostZoom']);    // avatar visible full-frame (no overlay, no glide)
const HOST_PUSH = 0.10;      // a host beat (not handing into a glide) gently pushes IN this far, from 1.0
const OPEN_SETTLE_S = 0.65;  // QUICK opening zoom-out (Ryan 2026-07-05): the pull-out is a fast
//                              VISUAL HOOK — it snaps from 1.1→1.0 in ~this long, starting on the
//                              first spoken word, then holds until the glide. Not a slow 2s drift.

// ONE SPOKEN BEAT = ONE SHOT (Ryan 2026-07-01: "the spoken script is the timeline that
// determines everything" — a cut may exist ONLY at a spoken-beat boundary, never inside one).
// Each beat in the plan IS a whole spoken beat, so the avatar motion per beat is exactly ONE
// move, no cuts inside it:
//   open     → the single pull-out (1.10→1.00), settling by ~OPEN_SETTLE_S, held to the SB end.
//   hostZoom → ONE continuous slow push-in across the whole spoken beat ("every hero beat
//              carries a continuous push-in zoom — never a frozen frame"). One move, no
//              reversal; the next SB's boundary cut resets the framing.
//   device   → the device owns the frame; the host slides (glide) or sits underneath (overlay).
// Consecutive host beats can't occur under the rotation (a device always separates them); if
// one ever does, it HOLDS at the pushed scale — never two moves in a row (Ryan 2026-06-30).
// BARE-CUT law (Ryan 2026-07-03): a plan with NO animations anywhere (no intro asset,
// no device keys, no glides) is an AUDIO-CLEANING pass — the camera does NOTHING. No
// open pull, no pushes, no reframes: the only change from the raw footage is the cuts.
const BARE_CUT = BEATS.every((b) =>
  b.style !== 'intro' && b.style !== 'glideR' && b.style !== 'glideL' &&
  !b.count && !b.snip && !b.pair && !b.merge && !b.roles && !b.upg && !b.sprint && !b.funnel && !b.closer && !b.section && !b.photo && !b.document && !b.diagramItems && !b.chips && !b.phrase);

// A glide is reserved for MEDIA/diagrams (photo, document, a diagram pack). Plain TEXT never
// splits the frame (Matthew, 2026-07-13): a caption beat keeps the host FULL-FRAME and overlays
// the words. So a glide span exists only when an actual glide animation matches this beat.
const hasGlideAnim = (b: Beat) => ANIMATIONS.some((a) => a.scenes.includes('glide') && a.match(b));

const SPANS: GlideSpan[] = (() => {
  const out: GlideSpan[] = [];
  for (let bi = 0; bi < BEATS.length; bi++) {
    const b = BEATS[bi];
    const nxt = BEATS[bi + 1];
    const start = b.style === 'open' ? 0 : f(b.start);
    if (BARE_CUT) { out.push({ start, state: 'hero', zoom: [1.0, 1.0] }); continue; }
    if (b.style === 'glideR' || b.style === 'glideL') {
      if (hasGlideAnim(b)) {
        // a DOCUMENT beat splits the frame: the host becomes a hard, full-height slice flush to
        // the edge (docR/docL) and the article fills the rest. Other media (photo) glides into
        // the rounded glass panel. NOT plain text — that never splits.
        const state = b.document ? (b.style === 'glideR' ? 'docR' : 'docL') : b.style;
        out.push({ start, state }); continue;
      }
      // TEXT-only beat: no split. Host stays full-frame and gently pushes in (the caption
      // overlays it over-the-shoulder), like any host beat.
      const nextGlide = !!nxt && (nxt.style === 'glideR' || nxt.style === 'glideL') && hasGlideAnim(nxt);
      out.push({ start, state: 'hero', zoomFrac: 1, zoomEase: 'linear', zoom: nextGlide ? [1.0, 1.0] : [1.0, 1.0 + HOST_PUSH] });
      continue;
    }
    if (b.style === 'open') { out.push({ start: 0, state: 'hero', zoom: [1.1, 1.0], zoomFrac: Math.min(1, OPEN_SETTLE_S / Math.max(b.dur, 0.5)), zoomEase: 'out' }); continue; }
    if (!BARE_HOST.has(b.style)) { out.push({ start, state: 'hero', zoom: [1.0, 1.0] }); continue; } // intro etc: overlay owns the camera; base holds at rest
    // ONE RULE (Ryan 2026-07-04): every host beat STARTS at REST (1.0 — the opening frame
    // is NEVER zoomed or cropped). A beat that hands into a GLIDE holds at 1.0 (ends
    // uncropped → the glide starts from the SAME framing, so it slides smoothly); any
    // other host beat gently pushes IN. One linear move, fully deterministic.
    const nextGlide = !!nxt && (nxt.style === 'glideR' || nxt.style === 'glideL');
    out.push({ start, state: 'hero', zoomFrac: 1, zoomEase: 'linear', zoom: nextGlide ? [1.0, 1.0] : [1.0, 1.0 + HOST_PUSH] });
  }
  return out;
})();

const O: React.FC<{ from: number; dur: number; z?: number; children: React.ReactNode }> = ({ from, dur, z = 42, children }) => (
  <Sequence from={from} durationInFrames={Math.max(dur, 1)} layout="none"><AbsoluteFill style={{ zIndex: z }}>{children}</AbsoluteFill></Sequence>
);

// Adaptive caption size: shrink the type as a caption gets denser so it ALWAYS fits its
// region. Deterministic — a pure function of the caption text.
const capChars = (cap: KCWord[]) => cap.reduce((n, w) => n + w.t.length + 1, 0);
const fitSize = (cap: KCWord[], base: number, min: number, target: number) =>
  Math.max(min, Math.round(base * Math.min(1, Math.sqrt(target / Math.max(capChars(cap), 1)))));

// The plugin lookup: the first (highest-priority) discovered animation that can render in
// this scene AND matches this beat's plan anchors. ANIMATIONS is pre-sorted by priority.
const pick = (b: Beat, scene: AnimScene) => ANIMATIONS.find((a) => a.scenes.includes(scene) && a.match(b));

export const AutoReel: React.FC = () => (
  <AbsoluteFill style={{ fontFamily: SANS, textTransform: 'lowercase', ['--accent-rgb' as string]: ACCENT_RGB } as React.CSSProperties}>
    {/* GREEN-SCREEN channels (bloomers): the animated flower field replaces the charcoal grid,
        and the host is the KEYED alpha video composited over it (transparent). Otherwise the
        base charcoal + opaque host. Framing is baked into the keyed clip (see greenscreen_key.py). */}
    <AbsoluteFill style={{ zIndex: 0 }}>{GREENSCREEN ? <FlowerBg bg={GREENSCREEN.background} flowers={GREENSCREEN.flowers} /> : <CharcoalBg />}</AbsoluteFill>
    <AbsoluteFill style={{ zIndex: Z.avatar }}><AvatarGlide src={GREENSCREEN ? GREENSCREEN.src : SRC} spans={SPANS} faceX={FACE_X} transparent={!!GREENSCREEN} /></AbsoluteFill>
    {BEATS.map((b, i) => {
      const start = f(b.start);
      const end = f(b.start + b.dur);
      const cap = (b.cap || []) as KCWord[];
      // intro: THE INTRO ASSET — tight-open → diagonal zoom-out + power phrase → whip-pan
      // into the official-logo zone, all camera moves derived from the spoken word times.
      // Opaque over the (audio-carrying) base avatar; owns SB1 from its first frame.
      if (b.style === 'intro') {
        const logos: IntroLogo[] = (b.chips || [])
          .map((c) => (LOGO_IMG[c.t] ? { ...LOGO_IMG[c.t], at: c.at } : null))
          .filter((x): x is IntroLogo => x !== null);
        return (
          <O key={i} from={start} dur={end - start} z={42}>
            <AbsoluteFill><CharcoalBg /></AbsoluteFill>
            <IntroStage src={SRC} from={b.start} durFrames={end - start} faceX={FACE_X} phrase={b.phrase as KCWord[] | undefined} logos={logos} />
          </O>
        );
      }
      // glides: a MEDIA/diagram beat slides the host aside (glass panel, or the document
      // split) and the open area carries that animation. A TEXT-only beat does NOT split —
      // the host stays full-frame (see SPANS) and the caption rides OVER-THE-SHOULDER, on the
      // side away from the face, highlighting important words with an accent underline.
      if (b.style === 'glideR' || b.style === 'glideL') {
        const anim = pick(b, 'glide');
        if (anim) {
          const openSide: 'left' | 'right' = b.style === 'glideR' ? 'left' : 'right';
          return (
            <O key={i} from={start} dur={end - start} z={Z.sideFill}>
              {anim.render({ b, start, end, f, scene: 'glide', side: openSide })}
            </O>
          );
        }
        const osSide = FACE_X >= 960 ? 'osL' : 'osR';   // over the shoulder opposite the face
        return (
          <O key={i} from={start} dur={end - start} z={Z.over}>
            <KineticCaption words={cap} from={b.start} size={fitSize(cap, 60, 44, 260)} dark side={osSide} leadF={5} />
          </O>
        );
      }
      // host beats (open / hostZoom): a matching overlay animation plays as a transparent
      // layer over the full-frame host, else nothing (host on camera with the single push).
      if (BARE_HOST.has(b.style)) {
        const anim = pick(b, 'host');
        if (!anim) return null;
        return (
          <O key={i} from={start} dur={end - start} z={Z.over}>
            {anim.render({ b, start, end, f, scene: 'host', side: 'left' })}
          </O>
        );
      }
      return null; // bare open / hostZoom / punch = host on camera with the single push, no overlay
    })}
  </AbsoluteFill>
);
