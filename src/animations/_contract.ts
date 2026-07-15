// THE ANIMATION PLUGIN CONTRACT.
// Every animation is a self-contained folder under src/animations/<kind>/ that default-exports
// ONE AnimModule. The renderer (AutoReel) never imports animations directly — it asks the
// registry (built by scanning this folder) which module matches a beat, and renders it.
//
// To ADD an animation: drop a folder with an index.tsx that default-exports an AnimModule,
// then regenerate the registry (scripts/build_anim_registry.mjs). No edit to AutoReel, no
// edit to a central list. To REMOVE one: delete its folder and regenerate. That is the whole
// plugin model — discovery by convention, single source of truth = the folders on disk.
import type React from 'react';
import type { Beat } from '../methodology/officialTestBeatPlan';

// Where an animation can render. The base engine owns the camera + host; an animation only
// fills the diagram region:
//   'glide' → the open half of a glide panel (host slid to one side)
//   'host'  → a transparent overlay while the host is full-frame on camera
export type AnimScene = 'glide' | 'host';

// Everything an animation needs to place itself on the beat's spoken timeline. Frames are
// 30fps ints; `f` converts seconds→frames; `side` is the OPEN side of a glide (ignored for host).
export type AnimContext = {
  b: Beat;
  start: number;                 // beat start, frames
  end: number;                   // beat end, frames
  f: (s: number) => number;      // seconds → frames
  scene: AnimScene;
  side: 'left' | 'right';
};

export type AnimModule = {
  kind: string;                  // the folder name / the classifier kind (e.g. 'count')
  description: string;           // "use me when…" — the SINGLE source for the picker's list
  category: string;              // coarse group for narrowing at scale (e.g. 'data', 'flow', 'brand')
  tags: string[];                // finer content-type hints the picker filters on before choosing
  scenes: AnimScene[];           // which scenes this animation can render in
  match: (b: Beat) => boolean;   // does this beat carry this animation's plan anchor?
  render: (c: AnimContext) => React.ReactNode;  // the diagram element (AutoReel wraps it)
  priority?: number;             // lower = matched first when two animations could both fit
                                 // (e.g. merge before stack); default 100
};
