#!/usr/bin/env python3
"""
Reaction-emphasis clip renderer for the matthew CS2 channel (Renyan-style).

For a REACTION clip (funny thing said / funny face / goofy reaction), the WHOLE FRAME
punches in on the top-left (where the facecam lives) — so the face gets bigger without any
compositing, keying, or split. It's just a zoom of the normal clip; nothing is re-laid-out.
Normal (skill) clips DON'T use this — they render full-frame at 1.0.

HARD RULES baked in:
  * The facecam / green screen are used EXACTLY AS RECORDED. We NEVER chroma-key the green
    screen (Matthew, 2026-07-15) — a full-frame zoom keeps it untouched by construction.
  * Audio is the music-free VOD Track only (never the Master Track) — copyright.

Output matches the normal clips (1920x1080 @60, H.264, stereo AAC) so clips concat cleanly.

Usage:
  python3 render_reaction_clip.py VOD START END OUT \
      [--zoom 0.5] [--anchor X,Y] [--audio-track 1] [--gain 22]

  --zoom  = fraction of the frame kept, then blown up to full (0.5 = the top-left QUARTER;
            smaller = punchier). --anchor = top-left corner of that crop in source px
            (default 0,0 = hug the top-left where the cam is).

Defaults are calibrated for the 7:14 stream recordings (2560x1440, facecam top-left).
Read audio track names with:
  ffprobe -v error -select_streams a:N -show_entries stream_tags=name  (use the 'VOD Track').
"""
import argparse, subprocess, sys

def build_filter(src_w, src_h, out_w, out_h, zoom, ax, ay):
    # crop keeps the source aspect (out is same aspect), anchored at (ax,ay), then scale to full
    cw = round(src_w * zoom); ch = round(src_h * zoom)
    cx = max(0, min(ax, src_w - cw)); cy = max(0, min(ay, src_h - ch))
    return f"[0:v:0]crop={cw}:{ch}:{cx}:{cy},scale={out_w}:{out_h}:flags=lanczos,setsar=1[v]"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("vod"); ap.add_argument("start"); ap.add_argument("end"); ap.add_argument("out")
    ap.add_argument("--zoom", type=float, default=0.5, help="fraction of the frame kept then blown up (0.5 = top-left quarter)")
    ap.add_argument("--anchor", default="0,0", help="X,Y top-left of the crop in source px (0,0 = top-left corner)")
    ap.add_argument("--src", default="2560,1440", help="source WxH (W,H)")
    ap.add_argument("--out-size", default="1920,1080", help="output WxH (W,H)")
    ap.add_argument("--audio-track", type=int, default=1, help="VOD Track audio stream index (music-free)")
    ap.add_argument("--gain", type=float, default=22.0, help="dB gain for the quiet VOD Track")
    a = ap.parse_args()
    sw, sh = map(int, a.src.split(",")); ow, oh = map(int, a.out_size.split(","))
    ax, ay = map(int, a.anchor.split(","))
    vf = build_filter(sw, sh, ow, oh, a.zoom, ax, ay)
    af = f"[0:a:{a.audio_track}]highpass=f=40,volume={a.gain}dB,alimiter=limit=0.9:level=false[a]"
    cmd = ["ffmpeg", "-v", "error", "-ss", a.start, "-to", a.end, "-i", a.vod,
           "-filter_complex", f"{vf};{af}", "-map", "[v]", "-map", "[a]",
           "-r", "60", "-c:v", "libx264", "-preset", "medium", "-crf", "19",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ac", "2", a.out, "-y"]
    print(f"reaction zoom: {a.zoom:.2f} (top-left), rendering...")
    sys.exit(subprocess.run(cmd).returncode)

if __name__ == "__main__":
    main()
