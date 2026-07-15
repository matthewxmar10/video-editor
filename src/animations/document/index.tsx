// DOCUMENT — a screenshot of a DOCUMENT / ARTICLE / news page / wiki page / pricing table shown
// as a HARD SPLIT-SCREEN with the host: the article FILLS one whole side of the frame edge-to-
// edge (top to bottom, no border, no card, no backdrop, no caption, no letterbox), and the host
// is a full-height camera slice flush to the other edge (no glass panel, no rounded corners, no
// background gap). Matthew's global rule for ALL channels: when the on-screen thing is a document
// (not a normal photo of a place/object), DON'T dress it up — just the article beside the camera.
//
// This is the plain sibling of the `photo` pack. Use `photo` for a real place/thing (Ken Burns,
// caption chip, rounded card). Use `document` for anything you'd READ.
//
// The host side is drawn by the base engine (AvatarGlide's docL/docR states, width SPLIT_HOST_W);
// this pack fills the REMAINING side, so the two meet at a single hard seam with no charcoal
// showing. The host layer sits ABOVE this one, so on entry the camera slides off the article to
// REVEAL it. The image cover-fills (never letterboxed) with a deliberately subtle push so it
// clears the always-building gate without reading as a showy effect — provide a screenshot
// cropped to roughly the panel's shape (a tall page can crop at the bottom; use fit:'top').
//
// DATA: the plan carries `document: { img, at, fit? }` on a glide beat (authored in the diagrams
// cache: {"scene":2,"anim":"document","img":"documents/rossmann-lcd.png","word":"pricing"}).
//   • `at`  — the spoken cue word's time (the panel is up from the beat's FIRST frame regardless;
//             it FILLS its side, so it never waits for a late pop that would flash a gap).
//   • `fit` — 'whole' (default): cover-fill anchored to the TOP. 'top': identical anchor, kept
//             as an explicit alias for "the head is what matters, the tail may crop."
import React from 'react';
import { Img, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig } from 'remotion';
import type { AnimModule, AnimContext } from '../_contract';
import { SPLIT_HOST_W } from '../../components/vc/style';

type DocData = { img: string; at: number; fit?: 'whole' | 'top' };

const DocumentPanel: React.FC<AnimContext> = ({ b, start, end, side }) => {
  const frame = useCurrentFrame();     // 0 at the beat's first frame
  const { fps, width, height } = useVideoConfig();
  const portrait = height > width;     // 9:16 short-form: host is full-bleed → doc is a top band
  const doc = (b as unknown as { document?: DocData }).document;
  if (!doc) return null;

  // Subtle, non-showy motion: a slow continuous push from 1.0 (anchored top so the head stays put)
  // plus a hair of drift. High-frequency text edges make even this small move clear the build gate
  // in every third, while staying visually calm — the article, not an effect. It fills its side
  // from frame 0 (the host wipe reveals it), so no fade-in that would flash a gap.
  const durF = Math.max(1, end - start);
  const t = frame / fps;
  const push = 1.0 + 0.04 * interpolate(frame, [0, durF], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const drift = Math.sin((t * Math.PI * 2) / 3.6) * 3;
  const settle = spring({ frame, fps, config: { damping: 200, stiffness: 200, mass: 0.6 }, durationInFrames: 10 });

  // Fill exactly the side the host does NOT occupy, so the seam lands with no charcoal gap.
  // Long-form: host is a SPLIT_HOST_W slice flush to one edge → doc fills the 1920-SPLIT_HOST_W
  // rest, full height. side 'left' = docR (host right) → doc left; 'right' = docL → doc right.
  const docW = width - SPLIT_HOST_W;
  const wrap: React.CSSProperties = portrait
    ? { position: 'absolute', left: 0, top: 0, width, height: Math.round(height * 0.56), overflow: 'hidden' }
    : { position: 'absolute', top: 0, height, width: docW, overflow: 'hidden',
        left: side === 'left' ? 0 : SPLIT_HOST_W };

  return (
    <div style={{ ...wrap, opacity: settle }}>
      <Img
        src={staticFile(doc.img)}
        style={{
          width: '100%', height: '100%',
          objectFit: 'cover',            // FILL edge-to-edge — never a letterbox / visible background
          objectPosition: 'center top',  // anchor the head of the document; a long page crops at the tail
          transform: `translateY(${drift}px) scale(${push})`, transformOrigin: 'center top',
        }}
      />
    </div>
  );
};

const mod: AnimModule = {
  kind: 'document',
  description: 'A screenshot of a DOCUMENT/ARTICLE the host references — a webpage, news page, wiki page, pricing table, or any screenshot of text you would READ — shown as a hard SPLIT-SCREEN: the article fills one whole side edge-to-edge (no card, border, backdrop, caption, or letterbox) and the host is a full-height camera slice flush to the other edge (no glass/rounded panel), facing into it. This is the plain sibling of `photo` (which is for a real place/thing, with a Ken Burns card). Use `document` for anything textual. Crop the screenshot to roughly the panel shape. Author as {scene:2 or 3, anim:document, img:documents/<file>, word:<spoken cue>, fit?:whole|top}.',
  category: 'media',
  tags: ['document', 'article', 'news', 'wiki', 'webpage', 'screenshot', 'table', 'text', 'page'],
  scenes: ['glide'],
  match: (b) => !!(b as unknown as { document?: unknown }).document,
  render: (c) => <DocumentPanel {...c} />,
  priority: 40,
};

export default mod;
