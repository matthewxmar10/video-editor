#!/usr/bin/env python3
"""
ACTION-CONDENSE mode for the matthew CS2 channel — a tighter condense than condense_game.py.

condense_game.py  = cut only DEAD AIR (quiet on both mic AND game). Keeps ~70-80% of a match.
condense_action.py = keep the ACTION and the TALK, cut the boring in-between. A ~48-min match
                     lands around 20-30 min (tunable). Built for a watchable standalone upload.

Why a second mode: in CS2 the game track is almost never silent (ambient, footsteps, chatter),
so a plain loudness gate keeps nearly everything. This mode instead detects COMBAT from the game
track's high-band onset density (gunfire = dense broadband transients; footsteps/ambient are not),
and keeps a round-context window around each fight, PLUS Matthew's mic and teammate voice-chat so
the funny/hype comms survive. Buy-time, quiet rotations, eco downtime and AFK get cut.

KEEP a moment when ANY of:
  * COMBAT  — game-audio high-band onset strength above the --combat-pct percentile (actual fights)
  * TALK    — Matthew's mic above --mic-thr (his commentary / reactions)
  * COMMS   — teammate voice chat above --vc-thr (funny / hype chatter)
Each kept region is padded (--lead before, --tail after) so you see the engagement start and the
outcome, and nearby regions merge (--merge-gap) so a round's fights read as one clip, not confetti.

AUDIO (default = stems mode): the final mix is REBUILT from the individual music-free tracks —
mic (a:2) + Discord/voice-chat (a:4) + game (a:3), never the Master track (music = copyright). Each
source is loudness-measured and gained to a target so they sit in a fixed balance: your mic on top,
Discord just under it, game as the bed underneath. The mic is high-passed + compressed so its wide,
spiky dynamics stop peaking; a master true-peak limiter guards the sum. No dynamic normalizer is used
anywhere, so nothing chases a target and ducks the mix. `--audio-mode vod` falls back to the old
single pre-mixed VOD-Track boost. Tune with --mic-lufs / --discord-lufs / --game-lufs.

HARD RULES (shared with the rest of the channel):
  * Final audio is music-free — built from mic+Discord+game stems (or the VOD Track), never the Master.
  * Facecam / green screen used exactly as recorded — nothing keyed, full frame kept.
  * Chronological order always; never regroup by category.

Tracks are identified by CONTENT when unnamed (OBS multitrack often exports bare "SoundHandler"):
run --probe to see per-track stats and confirm which index is VOD / mic / game / voice-chat before
trusting the defaults below.

Output: 1920x1080 @60 H.264 / stereo AAC.

Usage:
  python3 condense_action.py VOD OUT [--combat-pct 91] [--mic-thr -46] [--vc-thr -40]
                                     [--lead 2.0] [--tail 2.5] [--merge-gap 4.0] [--min-seg 4.0]
                                     [--plan-only] [--probe] [--preset veryfast]
  --combat-pct  keep game onsets above this percentile: lower = keep more action (88 looser, 91
                balanced, 94 tighter).  --plan-only prints kept length / clip count without rendering.
"""
import argparse, subprocess, sys, tempfile, os, wave
import numpy as np


def probe_dur(vod):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "default=nk=1:nw=1", vod], capture_output=True, text=True)
    return float(out.stdout.strip())


def n_audio_tracks(vod):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a",
                          "-show_entries", "stream=index", "-of", "csv=p=0", vod],
                         capture_output=True, text=True)
    return len([l for l in out.stdout.splitlines() if l.strip()])


def extract(vod, track, path, sr):
    subprocess.run(["ffmpeg", "-v", "error", "-i", vod, "-map", f"0:a:{track}", "-ac", "1",
                    "-ar", str(sr), path, "-y"], check=True)


def load_wav(path):
    w = wave.open(path, "rb"); sr = w.getframerate()
    a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    return a, sr


def env_db(a, sr, win=0.1):
    """100 ms RMS envelope in dBFS."""
    w = int(sr * win); n = len(a) // w
    if n == 0:
        return np.array([-120.0])
    a = a[:n * w].reshape(n, w)
    return 20 * np.log10(np.sqrt((a ** 2).mean(1) + 1e-12) + 1e-9)


def combat_intensity(game, sr, hop_s=0.05, win_s=0.05, hi_hz=1500.0, smooth_s=1.5):
    """High-band spectral-flux onset strength, smoothed. Gunfire lights this up; ambient does not.
    Returns (intensity[], hop_s) on a hop_s grid."""
    hop = int(hop_s * sr); win = int(win_s * sr)
    n = (len(game) - win) // hop
    if n <= 1:
        return np.zeros(1), hop_s
    frames = np.lib.stride_tricks.as_strided(
        game, shape=(n, win), strides=(game.strides[0] * hop, game.strides[0]))
    w = np.hanning(win)
    S = np.abs(np.fft.rfft(frames * w, axis=1))
    freqs = np.fft.rfftfreq(win, 1 / sr)
    hi = freqs > hi_hz
    hiflux = np.maximum(0, np.diff(S[:, hi], axis=0)).sum(axis=1)  # positive high-band flux
    k = max(1, int(smooth_s * sr / hop))
    ci = np.convolve(hiflux, np.ones(k) / k, mode="same")
    return ci, hop_s


def to_grid(env, grid_t, env_dt=0.1):
    """Nearest-sample resample of a 100 ms envelope onto the onset-grid times."""
    idx = np.clip((grid_t / env_dt).astype(int), 0, len(env) - 1)
    return env[idx]


def compute_segments(active, hop, lead, tail, merge_gap, min_seg):
    idx = np.where(active)[0]
    N = len(active)
    if len(idx) == 0:
        return [], N
    gap = int(merge_gap / hop)
    segs = []; s = prev = idx[0]
    for j in idx[1:]:
        if j - prev <= gap:
            prev = j
        else:
            segs.append([s, prev]); s = prev = j
    segs.append([s, prev])
    lf = int(lead / hop); tf = int(tail / hop)
    segs = [[max(0, a - lf), min(N, b + tf)] for a, b in segs]
    merged = [segs[0]]
    for a, b in segs[1:]:
        if a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    msf = int(min_seg / hop)
    merged = [s for s in merged if s[1] - s[0] >= msf]
    return merged, N


def measure_lufs(vod, track):
    """Integrated loudness (LUFS) of one audio track, via loudnorm's analysis pass.
    Audio-only (no video decode) so it's fast even on a long VOD."""
    out = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-vn", "-i", vod, "-map", f"0:a:{track}",
         "-af", "loudnorm=print_format=json", "-f", "null", "-"],
        capture_output=True, text=True)
    for line in out.stderr.splitlines():
        if '"input_i"' in line:
            return float(line.split(":")[1].strip().strip('",'))
    raise RuntimeError(f"could not measure loudness of track a:{track}")


def build_stem_audio(expr, mic_t, disc_t, game_t, g_mic, g_disc, g_game, master_makeup, tp_limit):
    """The approved CS2 stem mix, built on the SAME select expr as the video so every stem is cut
    identically then re-balanced. Music-free (mic + Discord + game only; never the Master track).

    - mic:     high-pass (rumble) -> compressor (tame the wide, spiky dynamics that were peaking)
               -> static gain to the mic LUFS target. A limiter on the master catches residual peaks.
    - discord: noise gate (so the big make-up gain doesn't amplify idle hiss) -> static gain.
    - game:    static gain (sits underneath as the bed).
    - master:  sum (no auto-attenuation) -> small make-up -> true-peak limiter. NO loudnorm anywhere,
               so nothing chases a target and ducks the mix (that was the end-of-clip cut-out bug)."""
    sel = lambda t: f"[0:a:{t}]aselect='{expr}',asetpts=N/SR/TB"
    mic = (f"{sel(mic_t)},highpass=f=80,"
           f"acompressor=threshold=-20dB:ratio=3:attack=5:release=150,volume={g_mic:.2f}dB[mic]")
    disc = f"{sel(disc_t)},agate=threshold=0.0018:range=-18dB,volume={g_disc:.2f}dB[disc]"
    game = f"{sel(game_t)},volume={g_game:.2f}dB[game]"
    mix = (f"[mic][disc][game]amix=inputs=3:normalize=0:duration=longest,"
           f"volume={master_makeup:.2f}dB,alimiter=limit={tp_limit}:level=false,aresample=48000[a]")
    return ";".join([mic, disc, game, mix])


def do_probe(vod, a):
    nt = n_audio_tracks(vod)
    print(f"{nt} audio tracks. Per-track envelope stats (identify VOD/mic/game/voice by content):")
    print(f"{'a:idx':>6} {'mean':>7} {'p50':>7} {'p90':>7} {'floor':>7} {'act>-60':>8}")
    with tempfile.TemporaryDirectory() as td:
        for i in range(nt):
            p = os.path.join(td, f"a{i}.wav")
            extract(vod, i, p, 8000)
            d = env_db(*load_wav(p))
            print(f"a:{i:>3} {d.mean():7.1f} {np.percentile(d,50):7.1f} {np.percentile(d,90):7.1f} "
                  f"{np.percentile(d,5):7.1f} {(d>-60).mean()*100:7.1f}%")
    print("\nVOD Track = full mix that goes QUIET in true dead air (music-free). Master Track keeps a\n"
          "continuous floor (music) even when everything else is silent — never use it for --audio-track.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("vod"); ap.add_argument("out", nargs="?", default="/dev/null")
    ap.add_argument("--combat-pct", type=float, default=91.0,
                    help="keep game onsets above this percentile (lower=more action kept)")
    ap.add_argument("--mic-thr", type=float, default=-46.0, help="keep where mic (talk) exceeds this dB")
    ap.add_argument("--vc-thr", type=float, default=-40.0, help="keep where voice chat (comms) exceeds this dB")
    ap.add_argument("--lead", type=float, default=2.0, help="seconds kept before each region (see the setup)")
    ap.add_argument("--tail", type=float, default=2.5, help="seconds kept after each region (see the outcome)")
    ap.add_argument("--merge-gap", type=float, default=4.0, help="bridge kept regions closer than this (s)")
    ap.add_argument("--min-seg", type=float, default=4.0, help="drop kept clips shorter than this (s)")
    ap.add_argument("--audio-mode", choices=["stems", "vod"], default="stems",
                    help="stems = rebalance mic/Discord/game from the individual tracks (default); "
                         "vod = the single pre-mixed music-free VOD Track (legacy)")
    ap.add_argument("--audio-track", type=int, default=1, help="vod mode: the pre-mixed VOD Track (music-free)")
    ap.add_argument("--mic-track", type=int, default=2)
    ap.add_argument("--game-track", type=int, default=3)
    ap.add_argument("--vc-track", type=int, default=4, help="Discord / teammate voice chat")
    # stems mode: per-source loudness targets (LUFS). Mic sits on top, Discord just under, game is the bed.
    ap.add_argument("--mic-lufs", type=float, default=-16.0)
    ap.add_argument("--discord-lufs", type=float, default=-19.5)
    ap.add_argument("--game-lufs", type=float, default=-24.0)
    ap.add_argument("--master-makeup", type=float, default=3.0, help="stems: final make-up gain (dB) before the limiter")
    ap.add_argument("--tp-limit", type=float, default=0.89, help="stems: master limiter ceiling (linear, ~-1 dBFS)")
    ap.add_argument("--gain", type=float, default=22.0, help="vod mode: blanket boost on the VOD Track (dB)")
    ap.add_argument("--out-size", default="1920,1080"); ap.add_argument("--fps", type=int, default=60)
    ap.add_argument("--preset", default="medium"); ap.add_argument("--crf", type=int, default=20)
    ap.add_argument("--plan-only", action="store_true")
    ap.add_argument("--probe", action="store_true", help="print per-track stats and exit")
    a = ap.parse_args()

    if a.probe:
        do_probe(a.vod, a); return

    dur = probe_dur(a.vod)
    with tempfile.TemporaryDirectory() as td:
        gp = os.path.join(td, "game.wav"); mp = os.path.join(td, "mic.wav"); vp = os.path.join(td, "vc.wav")
        extract(a.vod, a.game_track, gp, 22050)   # hi-SR for gunfire onset detection
        extract(a.vod, a.mic_track, mp, 8000)
        extract(a.vod, a.vc_track, vp, 8000)
        game, gsr = load_wav(gp)
        ci, hop = combat_intensity(game, gsr)
        grid_t = np.arange(len(ci)) * hop
        micG = to_grid(env_db(*load_wav(mp)), grid_t)
        vcG = to_grid(env_db(*load_wav(vp)), grid_t)
        n = min(len(ci), len(micG), len(vcG))
        ci, micG, vcG, grid_t = ci[:n], micG[:n], vcG[:n], grid_t[:n]

        ci_thr = np.percentile(ci, a.combat_pct)
        active = (ci > ci_thr) | (micG > a.mic_thr) | (vcG > a.vc_thr)
        merged, N = compute_segments(active, hop, a.lead, a.tail, a.merge_gap, a.min_seg)
        ivals = [(float(grid_t[s]), float(grid_t[min(e, N - 1)])) for s, e in merged]
        kept = sum(e - s for s, e in ivals)
        lens = [e - s for s, e in ivals] or [0]

        print(f"ACTION-CONDENSE  combat>p{a.combat_pct:.0f} | mic>{a.mic_thr}dB | vc>{a.vc_thr}dB | "
              f"lead {a.lead}s tail {a.tail}s merge {a.merge_gap}s")
        print(f"  source {dur/60:.1f} min  ->  kept {kept/60:.1f} min ({kept/dur*100:.0f}%)  "
              f"across {len(ivals)} clips ({len(ivals)-1} cuts), median {np.median(lens):.1f}s, "
              f"longest {max(lens):.1f}s")
        if a.plan_only or not ivals:
            return

        expr = "+".join(f"between(t,{s:.3f},{e:.3f})" for s, e in ivals)
        ow, oh = a.out_size.split(",")
        vf = (f"[0:v:0]select='{expr}',setpts=N/FRAME_RATE/TB,"
              f"scale={ow}:{oh}:flags=lanczos,fps={a.fps},setsar=1[v]")

        if a.audio_mode == "stems":
            print("measuring stem loudness (mic / Discord / game)...")
            m_mic = measure_lufs(a.vod, a.mic_track)
            m_disc = measure_lufs(a.vod, a.vc_track)
            m_game = measure_lufs(a.vod, a.game_track)
            g_mic, g_disc, g_game = a.mic_lufs - m_mic, a.discord_lufs - m_disc, a.game_lufs - m_game
            print(f"  mic {m_mic:.1f}->{a.mic_lufs} ({g_mic:+.1f}dB) | Discord {m_disc:.1f}->{a.discord_lufs} "
                  f"({g_disc:+.1f}dB) | game {m_game:.1f}->{a.game_lufs} ({g_game:+.1f}dB)")
            af = build_stem_audio(expr, a.mic_track, a.vc_track, a.game_track,
                                  g_mic, g_disc, g_game, a.master_makeup, a.tp_limit)
        else:
            af = (f"[0:a:{a.audio_track}]aselect='{expr}',asetpts=N/SR/TB,"
                  f"highpass=f=40,volume={a.gain}dB,alimiter=limit=0.9:level=false[a]")

        cmd = ["ffmpeg", "-v", "error", "-stats", "-i", a.vod, "-filter_complex", f"{vf};{af}",
               "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", a.preset, "-crf", str(a.crf),
               "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ac", "2", a.out, "-y"]
        print(f"rendering action-condensed game ({a.preset} crf{a.crf}, {a.audio_mode} audio)...")
        sys.exit(subprocess.run(cmd).returncode)


if __name__ == "__main__":
    main()
