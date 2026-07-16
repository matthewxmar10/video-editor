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
import argparse, subprocess, sys, tempfile, os, wave, shutil
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


def write_file_list(path, files):
    """concat-demuxer list of already-encoded segment files (joined with stream copy)."""
    with open(path, "w", encoding="utf-8") as f:
        for p in files:
            f.write("file '%s'\n" % os.path.abspath(p).replace("\\", "/").replace("'", r"'\''"))


def build_stem_audio(mic_t, disc_t, game_t, g_mic, g_disc, g_game, master_makeup, tp_limit):
    """The approved CS2 stem mix, applied to ALREADY-CUT audio (the concat demuxer did the cutting).
    Music-free (mic + Discord + game only; never the Master track).

    - mic:     high-pass (rumble) -> compressor (tame the wide, spiky dynamics that were peaking)
               -> static gain to the mic LUFS target. The master limiter catches residual peaks.
    - discord: noise gate (so the big make-up gain doesn't amplify idle hiss) -> static gain.
    - game:    static gain (sits underneath as the bed).
    - master:  sum (no auto-attenuation) -> small make-up -> true-peak limiter. NO loudnorm anywhere,
               so nothing chases a target and ducks the mix.

    No aselect/expression here — the graph is a fixed handful of filters regardless of clip count."""
    mic = (f"[0:a:{mic_t}]highpass=f=80,"
           f"acompressor=threshold=-20dB:ratio=3:attack=5:release=150,volume={g_mic:.2f}dB[mic]")
    disc = f"[0:a:{disc_t}]agate=threshold=0.0018:range=-18dB,volume={g_disc:.2f}dB[disc]"
    game = f"[0:a:{game_t}]volume={g_game:.2f}dB[game]"
    mix = (f"[mic][disc][game]amix=inputs=3:normalize=0:duration=longest,"
           f"volume={master_makeup:.2f}dB,alimiter=limit={tp_limit}:level=false,aresample=48000,"
           f"asetpts=PTS-STARTPTS[a]")
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


def _ffmpeg_progress(cmd, total_frames, progress, phase):
    """Run ffmpeg, streaming its -progress output so we can report frame progress for a long pass."""
    p = subprocess.Popen(cmd + ["-progress", "pipe:1", "-nostats"],
                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    for line in p.stdout:
        line = line.strip()
        if line.startswith("frame=") and progress and total_frames:
            try:
                progress(min(int(line[6:]), total_frames), total_frames, phase)
            except ValueError:
                pass
    return p.wait()


def render_and_join(segments, out, preset="medium", crf=20, fps=60, progress=None, log=None):
    """Cut each clip as its own accurately-seeked segment, then run ONE final pass that joins them and
    locks the whole thing to constant frame rate with continuous audio — so editors (DaVinci Resolve)
    don't drift audio behind the picture.  `segments` is a list of dicts {input, ss, dur, fc}; `fc` is a
    filter_complex outputting [v] and [a].  progress(done, total, phase) fires per clip ("cutting") and
    per frame of the final encode ("finalizing").  Shared by condense and the timeline assembler.

    Two passes on purpose: the per-segment cut can't be constant-frame-rate across joins (tiny gaps),
    and only a fresh -fps_mode cfr encode makes it uniform. Segments are near-lossless intermediates so
    the final pass, at the requested preset/crf, sets the real quality (one effective quality encode)."""
    out_dir = os.path.dirname(os.path.abspath(out)) or "."
    segdir = os.path.join(out_dir, ".ac_segs")
    os.makedirs(segdir, exist_ok=True)
    files = []
    n = len(segments)
    try:
        for i, sg in enumerate(segments):
            seg = os.path.join(segdir, f"seg_{i:05d}.ts")
            cmd = ["ffmpeg", "-v", "error", "-ss", f"{sg['ss']:.3f}", "-i", sg["input"],
                   "-t", f"{sg['dur']:.3f}", "-filter_complex", sg["fc"], "-map", "[v]", "-map", "[a]",
                   "-c:v", "libx264", "-preset", "ultrafast", "-crf", "16", "-pix_fmt", "yuv420p",
                   "-c:a", "aac", "-b:a", "256k", "-ac", "2", "-f", "mpegts", seg, "-y"]
            if subprocess.run(cmd).returncode:
                raise RuntimeError(f"clip {i+1}/{n} failed (input={os.path.basename(sg['input'])}, "
                                   f"start={sg['ss']:.1f}s)")
            files.append(seg)
            if progress:
                progress(i + 1, n, "cutting")
        listf = os.path.join(segdir, "list.txt")
        write_file_list(listf, files)
        if log:
            log("finalizing: locking to constant frame rate (for editors)...")
        total_frames = int(sum(sg["dur"] for sg in segments) * fps)
        final = ["ffmpeg", "-v", "error", "-f", "concat", "-safe", "0", "-i", listf,
                 "-fps_mode", "cfr", "-r", str(fps),
                 "-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-pix_fmt", "yuv420p",
                 "-af", "aresample=async=1:first_pts=0", "-c:a", "aac", "-b:a", "192k", "-ac", "2",
                 "-movflags", "+faststart", out, "-y"]
        if _ffmpeg_progress(final, total_frames, progress, "finalizing"):
            raise RuntimeError("final CFR pass failed")
    finally:
        shutil.rmtree(segdir, ignore_errors=True)
    return out


def default_opts(**over):
    """A namespace of condense knobs with the channel defaults, for callers without a command line
    (e.g. the Studio GUI). Override any field via keyword."""
    import types
    d = dict(combat_pct=91.0, mic_thr=-46.0, vc_thr=-40.0, lead=2.0, tail=2.5, merge_gap=4.0,
             min_seg=4.0, audio_mode="stems", audio_track=1, mic_track=2, game_track=3, vc_track=4,
             mic_lufs=-16.0, discord_lufs=-20.5, game_lufs=-24.0, master_makeup=3.0, tp_limit=0.79,
             gain=22.0, out_size="1920,1080", fps=60, preset="medium", crf=20, plan_only=False,
             probe=False, vod=None, out=None)
    d.update(over)
    return types.SimpleNamespace(**d)


def run_condense(a, progress=None, log=None):
    """Detect action, balance the stems, and render the condensed video. `a` carries the knobs
    (argparse namespace or default_opts()). progress(done, total) fires per clip; log(str) narrates.
    Returns the output path, or None for plan-only / nothing kept."""
    dur = probe_dur(a.vod)
    with tempfile.TemporaryDirectory() as td:
        gp = os.path.join(td, "game.wav"); mp = os.path.join(td, "mic.wav"); vp = os.path.join(td, "vc.wav")
        extract(a.vod, a.game_track, gp, 22050)
        extract(a.vod, a.mic_track, mp, 8000)
        extract(a.vod, a.vc_track, vp, 8000)
        game, gsr = load_wav(gp)
        ci, hop = combat_intensity(game, gsr)
        grid_t = np.arange(len(ci)) * hop
        micG = to_grid(env_db(*load_wav(mp)), grid_t)
        vcG = to_grid(env_db(*load_wav(vp)), grid_t)
        nn = min(len(ci), len(micG), len(vcG))
        ci, micG, vcG, grid_t = ci[:nn], micG[:nn], vcG[:nn], grid_t[:nn]
        active = (ci > np.percentile(ci, a.combat_pct)) | (micG > a.mic_thr) | (vcG > a.vc_thr)
        merged, N = compute_segments(active, hop, a.lead, a.tail, a.merge_gap, a.min_seg)
        ivals = [(float(grid_t[s]), float(grid_t[min(e, N - 1)])) for s, e in merged]
        kept = sum(e - s for s, e in ivals); lens = [e - s for s, e in ivals] or [0]
        if log:
            log(f"source {dur/60:.1f} min  ->  kept {kept/60:.1f} min ({kept/dur*100:.0f}%) across "
                f"{len(ivals)} clips, median {np.median(lens):.1f}s, longest {max(lens):.1f}s")
        if getattr(a, "plan_only", False) or not ivals:
            return None
        ow, oh = a.out_size.split(",")
        if a.audio_mode == "stems":
            if log:
                log("measuring stem loudness (mic / Discord / game)...")
            m_mic = measure_lufs(a.vod, a.mic_track)
            m_disc = measure_lufs(a.vod, a.vc_track)
            m_game = measure_lufs(a.vod, a.game_track)
            if log:
                log(f"  mic {m_mic:.1f}->{a.mic_lufs} | Discord {m_disc:.1f}->{a.discord_lufs} "
                    f"| game {m_game:.1f}->{a.game_lufs}")
            af = build_stem_audio(a.mic_track, a.vc_track, a.game_track,
                                  a.mic_lufs - m_mic, a.discord_lufs - m_disc, a.game_lufs - m_game,
                                  a.master_makeup, a.tp_limit)
        else:
            af = (f"[0:a:{a.audio_track}]highpass=f=40,volume={a.gain}dB,"
                  f"alimiter=limit=0.9:level=false,asetpts=PTS-STARTPTS[a]")
        vf = f"[0:v:0]scale={ow}:{oh}:flags=lanczos,fps={a.fps},setsar=1,setpts=PTS-STARTPTS[v]"
        fc = f"{vf};{af}"
        segments = [{"input": a.vod, "ss": s, "dur": e - s, "fc": fc} for s, e in ivals]
        if log:
            log(f"rendering {len(segments)} clips ({a.preset} crf{a.crf}, {a.audio_mode} audio)...")
        return render_and_join(segments, a.out, a.preset, a.crf, fps=a.fps, progress=progress, log=log)


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
    ap.add_argument("--discord-lufs", type=float, default=-20.5)
    ap.add_argument("--game-lufs", type=float, default=-24.0)
    ap.add_argument("--master-makeup", type=float, default=3.0, help="stems: final make-up gain (dB) before the limiter")
    ap.add_argument("--tp-limit", type=float, default=0.79,
                    help="stems: master limiter ceiling (linear; 0.79 lands ~-1.5 dBTP after inter-sample overshoot)")
    ap.add_argument("--gain", type=float, default=22.0, help="vod mode: blanket boost on the VOD Track (dB)")
    ap.add_argument("--out-size", default="1920,1080"); ap.add_argument("--fps", type=int, default=60)
    ap.add_argument("--preset", default="medium"); ap.add_argument("--crf", type=int, default=20)
    ap.add_argument("--plan-only", action="store_true")
    ap.add_argument("--probe", action="store_true", help="print per-track stats and exit")
    a = ap.parse_args()

    if a.probe:
        do_probe(a.vod, a); return

    def prog(done, total, phase=""):
        print(f"\r  {phase}: {done}/{total}      ", end="", flush=True)
    try:
        out = run_condense(a, progress=prog, log=print)
    except RuntimeError as ex:
        print(f"\nERROR: {ex}"); sys.exit(1)
    if out:
        print(f"\ndone -> {out}")


if __name__ == "__main__":
    main()
