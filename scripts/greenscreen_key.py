#!/usr/bin/env python3
"""greenscreen_key.py — DETECT a green screen behind the host and KEY IT OUT to a transparent
(alpha) video the renderer can composite over a custom background.

Built for the `bloomers` channel (Matthew, 2026-07-13): most of its footage is shot on a green
screen, lit unevenly so the green runs DARK→LIGHT. `chromakey` operates in YUV, keying on the
CHROMA distance from the key colour — largely independent of brightness — so a single key colour
plus a generous `similarity` removes the whole shadow-to-highlight green range in one pass.
`despill` then neutralises the green fringe/spill on the subject edges.

    python3 scripts/greenscreen_key.py <in.mp4> [out.webm] [--detect-only]
        [--key 0x3CB043] [--similarity 0.30] [--blend 0.12] [--despill 0.5]

Output is a VP9 webm with a real alpha channel (yuva420p) — Remotion's <OffthreadVideo transparent>
composites it directly. Audio is carried through (libopus) so the keyed clip stays a drop-in for
the cut. Exit 0 + prints "GREENSCREEN: yes/no" so the pipeline can decide whether to key at all.
"""
import subprocess, sys, os

def parse_opt(flag, default=None):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else default

def detect_green(path, frames=6):
    """Sample `frames` evenly, at 160x90 rgb24. Return (fraction, avg_key_rgb): the fraction of
    clearly-green pixels (green channel dominant AND bright enough to be screen, not dark
    clothing), and the AVERAGE colour of those green pixels — used as the key colour so the key
    auto-adapts to each shoot's exact green instead of a hardcoded guess. A green screen fills
    most of the frame behind the host, so a high fraction (>~0.35) means "key it"."""
    dur = probe_dur(path) or 2.0
    total_green = total = 0
    sr = sg = sb = 0
    for i in range(frames):
        t = max(0.0, dur * (i + 0.5) / frames)
        p = subprocess.run(['ffmpeg', '-nostdin', '-loglevel', 'error', '-ss', '%.3f' % t,
                            '-i', path, '-frames:v', '1', '-vf', 'scale=160:90', '-pix_fmt', 'rgb24',
                            '-f', 'rawvideo', '-'], capture_output=True)
        buf = p.stdout
        for j in range(0, len(buf) - 2, 3):
            r, g, b = buf[j], buf[j + 1], buf[j + 2]
            total += 1
            if g > 60 and g > r * 1.25 and g > b * 1.25:
                total_green += 1
                sr += r; sg += g; sb += b
    frac = (total_green / total) if total else 0.0
    key = '0x%02x%02x%02x' % (sr // total_green, sg // total_green, sb // total_green) if total_green else '0x2f9e45'
    return frac, key

def probe_dur(path):
    p = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                        '-of', 'default=nk=1:nw=1', path], capture_output=True, text=True)
    try:
        return float(p.stdout.strip())
    except ValueError:
        return None

def main():
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    src = sys.argv[1]
    if not os.path.exists(src):
        print('error: %s not found' % src); sys.exit(1)

    frac, auto_key = detect_green(src)
    is_green = frac >= 0.35
    print('GREENSCREEN: %s  (%.0f%% of sampled pixels read green; auto key colour %s)'
          % ('yes' if is_green else 'no', frac * 100, auto_key))
    if '--detect-only' in sys.argv:
        sys.exit(0 if is_green else 2)      # exit 2 = "no green screen" so a shell `if` can branch
    if not is_green:
        print('  no green screen detected — nothing to key (use --key to force).')
        if '--key' not in sys.argv:
            sys.exit(2)

    out = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith('--') else os.path.splitext(src)[0] + '-keyed.mov'
    # HUE-DOMINANCE KEY, split key/colour (tuned on Matthew's real screen, 2026-07-13). Journey:
    #  • A single-colour chroma key can't span this screen: the host's DARKER cast SHADOW stayed
    #    opaque as a second larger "cut-out" (Matthew's catch); widening ate the green-lit skin.
    #  • So we key on GREEN DOMINANCE (G > tol·max(R,B)) — removes bright green + shadow-green in
    #    one pass. But green LIGHT spilling on the cap-top/edges makes THEM green-dominant too, so
    #    a plain dominance key chewed the hat. Fix: a GREEN PULL-DOWN before the KEY decision drops
    #    that mild spill below the threshold (cap/edges survive) while the strong screen green still
    #    keys. A blown-out corner reads desaturated cyan (not green-dominant) → a 2nd OR-clause
    #    catches bright low-red cyan. The COLOUR is taken from the ORIGINAL (despilled) so the
    #    pull-down never tints the skin. Dark-cap mask + a close fill any residual cap speckles.
    tol = parse_opt('--tol', '1.08')              # green-dominance threshold; LOWER removes more green
    pull = parse_opt('--key-pulldown', '0.80')    # green ×this BEFORE the key only — de-spills cap/edges so
    #                                               they survive; the screen's strong green still keys
    despill = parse_opt('--despill', '0.5')       # green-fringe removal on the OUTPUT colour (from the original)
    dark = parse_opt('--protect-dark', '42')      # luma below this forced OPAQUE — fills cap speckles
    cast = 'colorchannelmixer=1.02:0:0:0:0:0.95:0:0:0:0:1:0'  # tiny warmth on the output (skin stays natural)
    # FRAMING: zoom-crop so the non-green edges (desk/monitor/cloth edge) fall outside frame —
    # "only the host is present". Biased slightly UP because the clutter sits along the bottom.
    zoom = float(parse_opt('--frame-zoom', '1.0'))
    if zoom > 1.001:
        crop = "crop=iw/%.4f:ih/%.4f:(iw-iw/%.4f)/2:(ih-ih/%.4f)*0.30,scale=1920:1080," % (zoom, zoom, zoom, zoom)
    else:
        crop = ""

    # geq alpha=0 where the pixel is background: green-dominant OR a bright low-red cyan hot-spot.
    # Commas inside the a='…' expression are backslash-escaped so the filtergraph parser keeps them.
    A = ("if(gt( gt(g(X,Y)\\,max(r(X,Y)\\,b(X,Y))*%s) + "
         "gt(g(X,Y)\\,180)*gt(b(X,Y)\\,150)*lt(r(X,Y)\\,g(X,Y)*0.85) \\, 0.5)\\,0\\,255)") % tol
    geq = "geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':a='%s'" % A
    # 3 branches off the framed source: [s0] key decision (pulled-down), [s1] dark-cap mask,
    # [s2] output colour (original despilled). matte = key OR cap, closed + feathered.
    fc = (
        "[0:v]%ssplit=3[s0][s1][s2];"
        "[s0]format=rgba,colorchannelmixer=1.0:0:0:0:0:%s:0:0:0:0:1:0,%s,format=rgba,alphaextract[ka];"
        "[s1]format=gray,lut=y='if(lt(val,%s),255,0)',gblur=sigma=2[dk];"
        "[ka][dk]blend=all_mode=lighten,dilation,dilation,dilation,erosion,erosion,erosion,median=radius=10,gblur=sigma=1.5[a];"
        "[s2]despill=type=green:mix=%s:expand=0.4,%s,format=rgba[rgb];"
        "[rgb][a]alphamerge,format=yuva444p10le[out]"
        % (crop, pull, geq, dark, despill, cast)
    )
    # ProRes 4444 (.mov) carries alpha reliably through ffmpeg AND Remotion's <OffthreadVideo
    # transparent> (VP9-alpha does not survive ffmpeg's decode). Audio carried through untouched.
    cmd = ['ffmpeg', '-y', '-i', src, '-filter_complex', fc, '-map', '[out]', '-map', '0:a?',
           '-c:v', 'prores_ks', '-profile:v', '4444', '-pix_fmt', 'yuva444p10le',
           '-c:a', 'copy', out]
    print('  keying → %s  (tol %s, key-pulldown %s, protect-dark<%s, despill %s, frame-zoom %s)' % (out, tol, pull, dark, despill, zoom))
    r = subprocess.run(cmd)
    if r.returncode != 0:
        print('error: ffmpeg keying failed'); sys.exit(1)
    print('✓ keyed alpha video: %s' % out)

if __name__ == '__main__':
    main()
