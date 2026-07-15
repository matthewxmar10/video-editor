#!/usr/bin/env python3
"""Word-level word timings via whisperX / faster-whisper.

Two modes, one venv (whisperx):

  default (--model small): whisperX forced alignment (~10-20ms accuracy, wav2vec2).
    Superior for landing an overlay ON the spoken word — use for the BEAT ANCHORS
    (the cut's word times). The wav2vec2 pass drops sentence punctuation.

  --fast: faster-whisper transcribe with word_timestamps (no alignment). Faster than the
    full align pass, and it KEEPS sentence punctuation on each word ("works." not "works")
    — which the dead-space/flub cutter needs (hostcut.detect_reset_spans walks back to the
    last sentence period to find where a flubbed take began). Use for the RAW cut pass.
    Uses the 'base' model (matches the shipped pipeline; --model overrides).

Run: ~/.venvs/whisperx/bin/python scripts/word_align_x.py <media.mp4> [--model small] [--fast]
Writes script/word-timings/<stem>-wx.json: [{word,start,end}, ...] (same shape either way).
"""
import json
import pathlib
import sys

DEVICE = 'cpu'


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if not args:
        sys.exit('usage: word_align_x.py <media.mp4> [--model small] [--fast]')
    src = pathlib.Path(args[0])
    fast = '--fast' in sys.argv
    # 'base' for the cut pass — matches the shipped pipeline byte-for-byte. base and small each
    # mishear DIFFERENT rushed 'reset reset' takes, and small's run-on timing on an aborted take
    # destabilizes the cut boundary, so no model wins; keep the tuned/stable base. A missed
    # rushed cue is caught by the beat map's LONG BEAT flag, never silently shipped. --model wins.
    model_name = 'base' if fast else 'small'
    if '--model' in sys.argv:
        i = sys.argv.index('--model')
        model_name = sys.argv[i + 1]

    if fast:
        # faster-whisper directly (it ships inside the whisperx venv). word_timestamps
        # attaches punctuation to each word token — the flub cutter depends on it.
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            sys.exit("faster_whisper not found — the whisperX environment isn't set up "
                     "(or the install failed midway).\nRun: bash scripts/setup.sh")
        model = WhisperModel(model_name, device=DEVICE, compute_type='int8')
        segments, _info = model.transcribe(str(src), word_timestamps=True)
        words = []
        for seg in segments:
            for w in (seg.words or []):
                words.append({'word': w.word.strip(), 'start': round(w.start, 3), 'end': round(w.end, 3)})
        label = 'faster-whisper transcribe (punctuated, for the cut)'
    else:
        try:
            import whisperx
        except ImportError:
            sys.exit("whisperx not found — the whisperX environment isn't set up "
                     "(or the install failed midway).\nRun: bash scripts/setup.sh")
        audio = whisperx.load_audio(str(src))
        model = whisperx.load_model(model_name, DEVICE, compute_type='int8')
        r = model.transcribe(audio, batch_size=16)
        align_model, meta = whisperx.load_align_model(language_code=r['language'], device=DEVICE)
        aligned = whisperx.align(r['segments'], align_model, meta, audio, DEVICE, return_char_alignments=False)
        words = []
        for seg in aligned['segments']:
            for w in seg.get('words', []):
                if 'start' in w and 'end' in w:
                    words.append({'word': str(w['word']).strip(), 'start': round(w['start'], 3), 'end': round(w['end'], 3)})
        label = 'whisperX forced alignment'

    out = pathlib.Path('script/word-timings') / f'{src.stem}-wx.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(words, indent=2, ensure_ascii=False) + '\n')
    print(f'wrote {out} — {len(words)} words ({label})')


if __name__ == '__main__':
    main()
