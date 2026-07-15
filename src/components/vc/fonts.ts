/**
 * SINGLE SOURCE OF TRUTH for the engine's type system. ONE voice for ALL on-screen text —
 * titles AND regular captions — in AKATAB, always lowercase (Matthew, 2026-07-13). Emphasis
 * is an accent UNDERLINE on important words, never a second face. Loaded via
 * @remotion/google-fonts so Remotion blocks render until the face is ready.
 */
import { loadFont as loadSans } from '@remotion/google-fonts/Akatab';

export const SANS = loadSans('normal', { weights: ['500', '600', '700', '800'], subsets: ['latin'] }).fontFamily; // Akatab — the single on-screen face
