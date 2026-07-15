/**
 * ENGINE CONFIG — the ONE file you edit to make the Core engine yours.
 *
 * The install is: set your brand color, drop in your host video, render. You should not
 * have to touch any component. Everything below flows out to the whole engine — change
 * `brand.accent` and every card, rim, icon, and glow re-skins to your color.
 *
 * (Fonts swap in `components/vc/fonts.ts`; your edit/script is a separate edit-plan —
 *  see methodology/edit-plan-contract.md.)
 */
export const ENGINE = {
  brand: {
    // YOUR color. The simplest rebrand = change `accent` (and, if you like, the two
    // gradient stops `lite`/`deep` to lighter/darker shades of it).
    accent: '#F7C715', //  icon · rim · emphasis · glow, on the dark surface
    lite: '#FFD83A', //    gradient TOP of a solid-accent surface
    deep: '#F0BC07', //    gradient BOTTOM
    ink: '#1A1C21', //     the BLACK mark that sits ON a solid-accent fill (keep it dark)
    label: '#F5F1EA', //   light label text on a dark card body
  },
  avatar: {
    src: 'host/video1.mp4', // your rendered host video, under public/ (e.g. public/host/<you>.mp4)
    faceX: 950, //          horizontal pixel of the host's face (drives glide framing)
  },
  canvas: { width: 1920, height: 1080, fps: 30 },
} as const;

/** '#F7C715' -> '247,199,21' (for rgba glows). */
export const hexToRgb = (hex: string): string => {
  const n = parseInt(hex.replace('#', ''), 16);
  return `${(n >> 16) & 255},${(n >> 8) & 255},${n & 255}`;
};
