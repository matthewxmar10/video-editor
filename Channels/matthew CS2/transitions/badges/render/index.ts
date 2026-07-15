import { registerRoot } from 'remotion';
import { BadgesRoot } from './Badges';

// Standalone Remotion entry for the CS2 stream badges. Kept separate from the
// engine's AutoReel entry (src/methodology/index.ts) so the deterministic
// talking-head pipeline is untouched. Rendered by ./build_badges.sh.
registerRoot(BadgesRoot);
