import React from 'react';
import {
  AbsoluteFill, Composition, Img, interpolate, spring, staticFile,
  useCurrentFrame, useVideoConfig,
} from 'remotion';
import { loadFont } from '@remotion/google-fonts/Archivo';
import { BADGE, COLORS, glow } from './style';

const { fontFamily: HEAVY } = loadFont('normal', { weights: ['700', '800'], subsets: ['latin'] });

// ── brand marks (recreated as inline SVG — no external assets) ──────────────
const TwitchMark: React.FC = () => (
  <svg viewBox="0 0 2400 2800" width="100%" height="100%">
    <path fill={COLORS.twitch} d="M500 0L0 500V2300H600V2800L1100 2300H1500L2400 1400V0H500ZM2200 1300L1800 1700H1400L1050 2050V1700H600V200H2200V1300Z" />
    <path fill={COLORS.twitch} d="M1700 550H1900V1150H1700V550Z" />
    <path fill={COLORS.twitch} d="M1150 550H1350V1150H1150V550Z" />
  </svg>
);
const YouTubeMark: React.FC = () => (
  <svg viewBox="0 0 48 34" width="100%" height="100%">
    <path fill={COLORS.yt} d="M47 5.2a6 6 0 0 0-4.2-4.2C39 0 24 0 24 0S9 0 5.2 1A6 6 0 0 0 1 5.2 62 62 0 0 0 0 17a62 62 0 0 0 1 11.8A6 6 0 0 0 5.2 33C9 34 24 34 24 34s15 0 18.8-1a6 6 0 0 0 4.2-4.2A62 62 0 0 0 48 17a62 62 0 0 0-1-11.8Z" />
    <path fill="#fff" d="M19 24l13-7-13-7z" />
  </svg>
);
const DiscordMark: React.FC = () => (
  <svg viewBox="0 0 71 55" width="100%" height="100%">
    <path fill={COLORS.discord} d="M60.1 4.9A58 58 0 0 0 45.4.5a.2.2 0 0 0-.2.1c-.6 1.1-1.3 2.6-1.8 3.8a54 54 0 0 0-16 0C26.9 3.1 26.2 1.7 25.6.6a.2.2 0 0 0-.2-.1A58 58 0 0 0 10.6 4.9a.2.2 0 0 0-.1.1C1.2 18.7-1.3 32.1 0 45.4a.2.2 0 0 0 .1.2 58 58 0 0 0 17.6 8.9.2.2 0 0 0 .2-.1c1.4-1.9 2.6-3.9 3.6-6a.2.2 0 0 0-.1-.3c-2-.7-3.8-1.6-5.6-2.6a.2.2 0 0 1 0-.4l1.1-.9a.2.2 0 0 1 .2 0 41 41 0 0 0 35 0 .2.2 0 0 1 .2 0l1.1.9a.2.2 0 0 1 0 .4c-1.8 1-3.7 1.9-5.6 2.6a.2.2 0 0 0-.1.3c1 2.1 2.3 4.1 3.6 6a.2.2 0 0 0 .2.1 58 58 0 0 0 17.6-8.9.2.2 0 0 0 .1-.2c1.6-15.3-2.4-28.6-10.4-40.4a.2.2 0 0 0-.1-.1ZM23.7 37.3c-3.5 0-6.4-3.2-6.4-7.1s2.8-7.1 6.4-7.1c3.6 0 6.5 3.2 6.4 7.1 0 3.9-2.8 7.1-6.4 7.1Zm23.6 0c-3.5 0-6.4-3.2-6.4-7.1s2.8-7.1 6.4-7.1c3.6 0 6.5 3.2 6.4 7.1 0 3.9-2.8 7.1-6.4 7.1Z" />
  </svg>
);

// Whole-badge in -> hold -> out envelope. `pop` gives the YouTube overshoot.
const useEnvelope = (pop: boolean) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const enter = spring({
    frame, fps,
    config: pop ? { damping: 10, stiffness: 170, mass: 0.7 } : { damping: 200, stiffness: 210, mass: 0.6 },
    durationInFrames: pop ? 22 : 16,
  });
  const exitStart = BADGE.D - 22;
  const exit = interpolate(frame, [exitStart, BADGE.D - 2], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const opacity = Math.max(0, enter) * (1 - exit);
  const ty = (1 - Math.min(1, enter)) * 42 + exit * 24;
  const scaleIn = pop ? interpolate(enter, [0, 1], [0.6, 1]) : interpolate(Math.min(1, enter), [0, 1], [0.94, 1]);
  const scale = scaleIn * (1 - exit * 0.05);
  return { frame, fps, opacity, ty, scale };
};

type ShellProps = {
  accent: string;
  kicker: React.ReactNode;
  title: string;
  Mark: React.FC;
  anchorY: number;
  pop?: boolean;
  ripple?: boolean;
  live?: boolean;
  glitch?: boolean;
  weapons?: boolean;
};

const Badge: React.FC<ShellProps> = ({ accent, kicker, title, Mark, anchorY, pop, ripple, live, glitch, weapons }) => {
  const { frame, fps, opacity, ty, scale } = useEnvelope(!!pop);
  const t = frame / fps;

  // idle life
  const livePulse = live ? 0.4 + 0.6 * (0.5 + 0.5 * Math.sin(t * Math.PI * 2 * 0.9)) : 1;
  const bell = pop ? Math.sin(Math.max(0, frame - 8) * 0.9) * Math.exp(-Math.max(0, frame - 8) / 10) * 14 : 0;
  const rip = ripple ? interpolate(frame, [4, 40], [0.4, 2.4], { extrapolateRight: 'clamp' }) : 0;
  const ripOp = ripple ? interpolate(frame, [4, 40], [0.5, 0], { extrapolateRight: 'clamp' }) : 0;
  // discord: brief rgb-split flicker mid-hold
  const g = glitch && (frame % 54 > 50) ? 1 : 0;
  const rgb = g ? `-2px 0 #ff004c, 2px 0 #00e5ff` : `0 0 26px ${accent}88`;
  const gx = g ? (frame % 2 === 0 ? -4 : 4) : 0;

  // weapon slide-in (Twitch bookends, facing inward)
  const wk = spring({ frame: frame - 3, fps, config: { damping: 200, stiffness: 200, mass: 0.6 }, durationInFrames: 18 });
  const akX = interpolate(wk, [0, 1], [-46, 0]);
  const scX = interpolate(wk, [0, 1], [46, 0]);

  return (
    <AbsoluteFill>
      <div style={{
        position: 'absolute', left: '50%', top: `${anchorY * 100}%`,
        transform: `translate(-50%,-50%) translateY(${ty}px) translateX(${gx}px) scale(${scale})`,
        opacity,
      }}>
        <div style={{
          position: 'relative', display: 'inline-flex', alignItems: 'center', gap: 30,
          padding: '30px 54px', borderRadius: 26, background: COLORS.glass,
          border: `1px solid ${COLORS.border}`,
          boxShadow: `0 30px 70px rgba(0,0,0,0.6), 0 0 0 1px rgba(255,255,255,0.03) inset`,
          fontFamily: HEAVY,
        }}>
          {/* accent rail */}
          <div style={{ position: 'absolute', left: 0, top: 16, bottom: 16, width: 7, borderRadius: 7, background: accent, boxShadow: `0 0 22px ${accent}` }} />

          {/* weapon bookends */}
          {weapons && (
            <>
              <Img src={staticFile('badges/ak47.png')} style={{
                position: 'absolute', right: '100%', top: '50%', width: 420, opacity: wk,
                transform: `translate(${58 + akX}px,-50%) scaleX(-1) rotate(6deg)`,
                filter: glow(accent),
              }} />
              <Img src={staticFile('badges/scythe.png')} style={{
                position: 'absolute', left: '100%', top: '50%', width: 300, opacity: wk,
                transform: `translate(${-66 + scX}px,-50%) rotate(-7deg)`,
                filter: glow(accent),
              }} />
            </>
          )}

          {/* icon */}
          <div style={{ position: 'relative', width: 92, height: 92, flex: '0 0 auto', display: 'grid', placeItems: 'center', filter: glow(accent), transform: `rotate(${bell}deg)`, transformOrigin: '60% 40%' }}>
            {ripple && <div style={{ position: 'absolute', left: '50%', top: '50%', width: 150, height: 150, borderRadius: '50%', border: `5px solid ${accent}`, transform: `translate(-50%,-50%) scale(${rip})`, opacity: ripOp }} />}
            <Mark />
          </div>

          {/* text */}
          <div style={{ display: 'flex', flexDirection: 'column', lineHeight: 1 }}>
            <div style={{ fontWeight: 800, fontSize: 20, letterSpacing: '0.26em', textTransform: 'uppercase', color: accent, marginBottom: 13, display: 'flex', alignItems: 'center', gap: 12 }}>
              {live && <span style={{ width: 17, height: 17, borderRadius: '50%', background: '#ff2d2d', boxShadow: '0 0 12px #ff2d2d', opacity: livePulse }} />}
              {kicker}
            </div>
            <div style={{ fontWeight: 800, fontSize: 52, letterSpacing: '-0.01em', color: COLORS.ink, textShadow: rgb }}>
              {title}
            </div>
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};

const Twitch: React.FC = () => (
  <Badge accent={COLORS.twitch} Mark={TwitchMark} kicker="live on twitch" title="recorded live on twitch" anchorY={0.24} live weapons />
);
const Subscribe: React.FC = () => (
  <Badge accent={COLORS.yt} Mark={YouTubeMark} kicker="new video" title="subscribe" anchorY={0.5} pop ripple />
);
const Discord: React.FC = () => (
  <Badge accent={COLORS.discord} Mark={DiscordMark} kicker="community" title="join the discord" anchorY={0.78} glitch />
);

export const BadgesRoot: React.FC = () => {
  const base = { durationInFrames: BADGE.D, fps: BADGE.fps, width: BADGE.W, height: BADGE.H } as const;
  return (
    <>
      <Composition id="Badge-Twitch" component={Twitch} {...base} />
      <Composition id="Badge-Subscribe" component={Subscribe} {...base} />
      <Composition id="Badge-Discord" component={Discord} {...base} />
    </>
  );
};
