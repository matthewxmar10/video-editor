/**
 * LOCKED STYLE TOKENS — the single source of truth for the engine's look.
 * Components read from here; the brand values themselves come from engine.config
 * (`brand.accent` is the one rebrand knob). Change a value here and the whole
 * style shifts consistently; never inline a color in a component.
 */

import { ENGINE, hexToRgb } from '../../engine.config';

export const FPS = ENGINE.canvas.fps;
export const CANVAS = { w: ENGINE.canvas.width, h: ENGINE.canvas.height } as const;

/** DOCUMENT SPLIT-SCREEN: width (px, in the 1920 frame) of the hard-edged, full-height host
 *  slice on a document beat — the rest is the full-bleed article. The host is flush to the
 *  frame edge with NO glass panel / rounded corners (the `document` pack + AvatarGlide's
 *  docL/docR states share this so the seam lands exactly, with no charcoal gap). */
export const SPLIT_HOST_W = 720;

/** The brand accent as an RGB triple, for rgba() glows/shadows that vary their alpha. */
export const ACCENT_RGB = hexToRgb(ENGINE.brand.accent);
/** A brand-accent glow at the given alpha — use this everywhere instead of a hardcoded
 *  rgba(var(--accent-rgb,247,199,21),…) literal, so changing engine.config `accent` re-skins every glow. */
export const glow = (a: number | string) => `rgba(${ACCENT_RGB},${a})`;

/** Shot-size diagram side-fill geometry. `left`/`capX` are per open-canvas side. */
export const DIAGRAM = {
  w: 760, h: 560, top: 150, containerW: 1040, containerH: 700,
  leftByOpen: { l: 60, r: CANVAS.w - 1100 } as const,
  capXByOpen: { l: 120, r: CANVAS.w - 1000 } as const,
} as const;

/** CREME content palette (light stages — kept for KineticCaption's light mode). */
export const CREME = {
  bg1: '#F4ECDA', // top of the cream gradient
  bg2: '#ECD7B8', // bottom (warmer)
  ink: '#2A2017', // headline / label text
  inkDim: 'rgba(42,32,23,0.55)',
  coral: '#D97757', // brand accent (icons, connectors)
  teal: '#2E8B82', // secondary emphasis
  card: '#FFFFFF',
  chip: '#F4EFE5', // icon-chip fill
  gridLine: 'rgba(255,251,243,0.55)', // subtle graph-paper texture
  cardShadow: '0 34px 70px rgba(80,60,30,0.24)',
  chipShadow: '0 12px 24px rgba(80,60,30,0.16)',
} as const;

/** CHARCOAL content palette — the live skin (charcoal grid + yellow glow). Keeps
    captions/cards legible + premium on dark: normal caption text is light `ink`,
    coral brightened so it pops (not muddy). Vetted by the charcoal design panel. */
export const CREME_DARK = {
  ink: '#EFEAE0',                       // normal caption / label text
  inkDim: 'rgba(239,234,224,0.60)',
  coral: '#E8916F',                     // brightened coral — pops on charcoal
  teal: '#2E8B82',
  card: '#FFFFFF',
  cardText: '#2A2017',                  // card text sits on a white card, not charcoal
  chip: '#F4EFE5',
  cardBorder: 'rgba(245,243,238,0.12)', // faint hairline so a white card never bleeds into the radial top
  cardShadow: '0 30px 64px rgba(0,0,0,0.58), 0 1px 0 0 rgba(255,255,255,0.7) inset',
  chipShadow: '0 12px 24px rgba(0,0,0,0.45)',
} as const;

/** GOLD/YELLOW accent — the premium GLOW kit (Ryan 2026-06-28). Yellow #F7C715 is
    LIGHT, so it behaves like a light SOURCE on dark. Hard rule, never crossed: a DARK
    surface gets a yellow/white mark; a YELLOW surface gets a BLACK mark — never white
    on yellow (~1.4:1), never yellow on yellow. Sourced from engine.config
    (`brand.accent` is the one rebrand knob). */
export const GOLD = {
  yellow: ENGINE.brand.accent,
  lite: ENGINE.brand.lite,
  deep: ENGINE.brand.deep,
  ink: ENGINE.brand.ink,
  label: ENGINE.brand.label,
} as const;

/** z-index layers (lock the compositing order). */
export const Z = {
  base: 0, // the constant CharcoalBg
  broll: 10, // full-screen media under the avatar layer
  sideFill: 20, // glide-panel animations in the open half
  avatar: 30, // AvatarGlide
  over: 40, // scene-1 overlay animations over the full-frame host
  card: 50, // reserved top layer
  fade: 90, // final fade-to-black
} as const;

export const sec = (s: number) => Math.round(s * FPS);
