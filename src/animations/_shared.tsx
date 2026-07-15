// Shared render helpers used by MORE THAN ONE animation module (and by the base intro for
// LOGO_IMG). Kept out of any single animation so no module depends on another. Moved here
// verbatim from AutoReel during the plugin refactor — behaviour is identical.
import React from 'react';
import { useCurrentFrame } from 'remotion';
import { Eye, DollarSign, Sparkles, Package, TrendingUp, Zap, Target, Repeat, Layers, Rocket, Star, Gauge, Clapperboard, AudioLines, type LucideIcon } from 'lucide-react';

// A full-stage (1920x1080) animation scaled into a glide panel, centered on the open half.
// The scale shrinks the inner motion below the build floor, so the wrapped stage itself
// BREATHES and drifts (ALWAYS-BUILDING at panel scale).
export const PanelWrap: React.FC<{ side: 'left' | 'right'; children: React.ReactNode }> = ({ side, children }) => {
  const fr = useCurrentFrame();
  const s = 0.58 * (1 + 0.018 * Math.sin((fr / 30) * Math.PI * 2 / 3.1));
  const dy = Math.sin((fr / 30) * Math.PI * 2 / 2.6) * 7;
  const cx = side === 'left' ? 620 : 1300;
  return (
    <div style={{ position: 'absolute', left: cx - (1920 * s) / 2, top: 540 - (1080 * s) / 2 + 12 + dy, width: 1920, height: 1080, transform: `scale(${s})`, transformOrigin: 'top left' }}>
      {children}
    </div>
  );
};

// Deterministic keyword -> Lucide icon for tour/diagram cards: a fixed dictionary lookup
// (pure function of the label) with a HASHED fallback, so an unmapped word still gets a
// stable, varied icon — never random, so the edit stays byte-reproducible.
const ICONS: Record<string, LucideIcon> = {
  views: Eye, view: Eye, watch: Eye, watching: Eye, audience: Eye,
  offer: DollarSign, offers: DollarSign, sell: DollarSign, sells: DollarSign, sales: DollarSign,
  money: DollarSign, earn: DollarSign, revenue: DollarSign, profit: DollarSign,
  free: Sparkles, ai: Sparkles, clean: Sparkles, variety: Sparkles,
  wrap: Package, package: Package, product: Package,
  fast: Zap, speed: Zap, quick: Zap, simple: Layers, simplicity: Layers,
  scale: TrendingUp, grow: TrendingUp, growth: TrendingUp,
  repeatable: Repeat, repeat: Repeat, loop: Repeat, deterministic: Target,
  launch: Rocket, best: Star, quality: Star, proof: Gauge,
  broll: Clapperboard, footage: Clapperboard,
  claude: Sparkles, claudecode: Sparkles, remotion: Clapperboard, whisperx: AudioLines, whisper: AudioLines,
};
const GENERIC: LucideIcon[] = [Sparkles, Zap, Star, Target, TrendingUp, Layers];
export const iconFor = (label: string): LucideIcon => {
  const k = label.toLowerCase().replace(/[^a-z]/g, '');
  if (ICONS[k]) return ICONS[k];
  let h = 0; for (let i = 0; i < k.length; i++) h = (h * 31 + k.charCodeAt(i)) >>> 0;
  return GENERIC[h % GENERIC.length];
};

// Official logo files for name-drop reveals (relative to public/). Used by the intro
// (base) and by the merge/stack/roles animations. ICONS ONLY, no wordmarks.
export const LOGO_IMG: Record<string, { img: string; label?: string; w?: number; tile?: boolean; glow?: string }> = {
  Claude: { img: 'logos/claude-mark.svg', w: 250, glow: 'rgba(255,138,80,0.55)' },
  Remotion: { img: 'logos/remotion-icon.png', w: 240, glow: 'rgba(66,140,255,0.5)' },
  WhisperX: { img: 'logos/whisperx.svg', w: 230, glow: 'rgba(247,199,21,0.45)' },
};
