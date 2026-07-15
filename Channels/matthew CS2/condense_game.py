#!/usr/bin/env python3
"""
CONDENSE mode for the matthew CS2 channel — a second editing mode alongside the highlight reel.

Highlight mode  = pull only the best moments (short reel).
Condense mode   = keep MOST of the game as a standalone video, only cutting DEAD AIR
                  (stretches with no talking AND no game action). A ~40-min game becomes ~20-30.

How "dead air" is decided (audio-driven, VOD-only):
  * KEEP a moment if there's game ACTION (Game Audio track loud enough: footsteps/shots/combat)
    OR TALKING (Mic/Voice track fires). Deaths, downtime-with-action, tense holds are all kept.
  * CUT a stretch only if it's quiet on BOTH for at least --min-sil seconds (buy-time standing
    around, AFK, long silent walks, dead-and-nothing-happening).
Segments are padded and near-ones merged so cuts aren't choppy or clip speech.

HARD RULES (shared with the rest of the channel):
  * Final audio = the music-free **VOD Track** (never the Master Track) — copyright.
  * Facecam/green screen used exactly as recorded — nothing keyed, full frame kept.

Output: 1920x1080 @60 H.264 / stereo AAC.

Usage:
  python3 condense_game.py VOD OUT [--game-thr -68] [--mic-thr -62] [--min-sil 1.8]
                                    [--pad 0.4] [--merge-gap 1.0] [--plan-only]
  --game-thr  dB: lower = keep more (‑72 keep-more, ‑68 balanced, ‑64 tighter, ‑60 aggressive)
  --plan-only prints the trim plan (length/segments) without rendering — use it to pick a setting.
"""
import argparse, subprocess, sys, tempfile, os, wave
import numpy as np

def probe_dur(vod):
    out = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration",
                          "-of","default=nk=1:nw=1",vod],capture_output=True,text=True)
    return float(out.stdout.strip())

def extract(vod, track, path, sr=8000):
    subprocess.run(["ffmpeg","-v","error","-i",vod,"-map",f"0:a:{track}","-ac","1",
                    "-ar",str(sr),path,"-y"],check=True)

def env_db(a, sr, win=0.1):
    w=int(sr*win); n=len(a)//w; a=a[:n*w].reshape(n,w)
    return 20*np.log10(np.sqrt((a**2).mean(1)+1e-12)+1e-9)

def load_wav(path):
    w=wave.open(path,"rb"); sr=w.getframerate()
    return np.frombuffer(w.readframes(w.getnframes()),dtype=np.int16).astype(np.float32)/32768.0, sr

def compute_intervals(mdb, gdb, fs, game_thr, mic_thr, pad, merge_gap, min_sil):
    N=min(len(mdb),len(gdb)); mdb,gdb=mdb[:N],gdb[:N]
    active=(gdb>game_thr)|(mdb>mic_thr)
    idx=np.where(active)[0]
    if len(idx)==0: return [], N
    gap=int(merge_gap/fs)
    segs=[]; s=prev=idx[0]
    for j in idx[1:]:
        if j-prev<=gap: prev=j
        else: segs.append([s,prev]); s=prev=j
    segs.append([s,prev])
    pf=int(pad/fs); mf=int(min_sil/fs)
    segs=[[max(0,a-pf),min(N,b+pf)] for a,b in segs]
    merged=[segs[0]]
    for a,b in segs[1:]:
        if a-merged[-1][1]<mf: merged[-1][1]=b
        else: merged.append([a,b])
    return [(a*fs, b*fs) for a,b in merged], N

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("vod"); ap.add_argument("out")
    ap.add_argument("--game-thr",type=float,default=-68.0)
    ap.add_argument("--mic-thr",type=float,default=-62.0)
    ap.add_argument("--min-sil",type=float,default=1.8,help="only cut quiet gaps at least this long (s)")
    ap.add_argument("--pad",type=float,default=0.4,help="keep this much around active audio (s)")
    ap.add_argument("--merge-gap",type=float,default=1.0,help="bridge active regions closer than this (s)")
    ap.add_argument("--mic-track",type=int,default=2); ap.add_argument("--game-track",type=int,default=3)
    ap.add_argument("--audio-track",type=int,default=1,help="final audio = VOD Track (music-free)")
    ap.add_argument("--gain",type=float,default=22.0)
    ap.add_argument("--out-size",default="1920,1080"); ap.add_argument("--fps",type=int,default=60)
    ap.add_argument("--plan-only",action="store_true")
    a=ap.parse_args()

    dur=probe_dur(a.vod)
    with tempfile.TemporaryDirectory() as td:
        mp=os.path.join(td,"m.wav"); gp=os.path.join(td,"g.wav")
        extract(a.vod,a.mic_track,mp); extract(a.vod,a.game_track,gp)
        mic,sr=load_wav(mp); game,_=load_wav(gp)
        mdb=env_db(mic,sr); gdb=env_db(game,sr); fs=0.1
        ivals,N=compute_intervals(mdb,gdb,fs,a.game_thr,a.mic_thr,a.pad,a.merge_gap,a.min_sil)
        kept=sum(b-a for a,b in ivals)
        print(f"TRIM PLAN  game>{a.game_thr}dB | mic>{a.mic_thr}dB | min-sil {a.min_sil}s")
        print(f"  source {dur/60:.1f} min  ->  kept {kept/60:.1f} min ({kept/dur*100:.0f}%)  "
              f"across {len(ivals)} segments, {len(ivals)-1} cuts removing {(dur-kept)/60:.1f} min")
        if a.plan_only or not ivals:
            return
        expr="+".join(f"between(t,{s:.3f},{e:.3f})" for s,e in ivals)
        ow,oh=a.out_size.split(",")
        vf=(f"[0:v:0]select='{expr}',setpts=N/FRAME_RATE/TB,"
            f"scale={ow}:{oh}:flags=lanczos,fps={a.fps},setsar=1[v]")
        af=(f"[0:a:{a.audio_track}]aselect='{expr}',asetpts=N/SR/TB,"
            f"highpass=f=40,volume={a.gain}dB,alimiter=limit=0.9:level=false[a]")
        cmd=["ffmpeg","-v","error","-stats","-i",a.vod,"-filter_complex",f"{vf};{af}",
             "-map","[v]","-map","[a]","-c:v","libx264","-preset","medium","-crf","20",
             "-pix_fmt","yuv420p","-c:a","aac","-b:a","192k","-ac","2",a.out,"-y"]
        print("rendering condensed game...")
        sys.exit(subprocess.run(cmd).returncode)

if __name__=="__main__":
    main()
