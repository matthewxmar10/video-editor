import React from 'react';
import { Composition } from 'remotion';
import { AutoReel, AUTO_FRAMES } from './AutoReel';
import { AutoReelVertical, AUTO_FRAMES_V } from './AutoReelVertical';

// LIVE registry. The editing engine renders ONE composition — AutoReel, the deterministic
// beat-and-glide renderer driven by the generated officialTestBeatPlan.ts. The superseded reels
// and the per-component design-benches (the *Lab compositions) were moved to ./archive on
// 2026-07-01 so this registry shows only the live path; git history preserves them, and to bring
// one back just move its file up a level and re-register it here.
export const MethodologyRoot: React.FC = () => {
  return (
    <>
      {/* DETERMINISTIC auto-edit — rendered straight from the computed beat plan (build_matched_plan.py). */}
      <Composition id="AutoReel" component={AutoReel} durationInFrames={AUTO_FRAMES} fps={30} width={1920} height={1080} />
      {/* SHORT-FORM (9:16) — same plan, vertical layout. */}
      <Composition id="AutoReelVertical" component={AutoReelVertical} durationInFrames={AUTO_FRAMES_V} fps={30} width={1080} height={1920} />
    </>
  );
};
