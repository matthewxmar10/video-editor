#!/usr/bin/env python3
"""Subject-image sourcing — the REAL-IMAGERY tier of the drawing layer (Ryan 2026-07-02:
"why generate a random player instead of getting the real picture").

Resolution order for a named subject:
  1. assets/people/<slug>.(png|jpg)  — an image the editor dropped in ALWAYS wins.
  2. Wikipedia lead image for the name (people/teams/things with a page) — the child's-play
     path: the photo everyone means. Attribution is the caller's job (receipt.json).
  3. Wikimedia Commons file search (for concepts: "referee red card", "wooden gavel").
Then: rembg background removal (the pipeline's existing venv) + the one-pass brand duotone
(alpha-preserving variant of the approved ConceptPair recipe).

    python3 scripts/fetch_subject_image.py "Christian Pulisic" public/cutouts/puli-duo.png
    python3 scripts/fetch_subject_image.py --search "referee red card football" public/cutouts/red-duo.png
    python3 scripts/fetch_subject_image.py --no-duotone "Folarin Balogun" out.png   # keep true color

Deterministic given the same web responses; the OUTPUT file is the committed artifact —
re-runs are only needed when you want a different photo.
"""
import json
import os
import re
import subprocess
import sys
import urllib.parse

UA = 'yta-clone-editor/1.0 (contact: repo owner)'
REMBG = os.path.expanduser('~/.venvs/rembg/bin/python')
DUO = ("format=rgba,hue=s=0,eq=contrast=1.18:brightness=0.012,"
       "colorchannelmixer=rr=1.0:gg=0.80:bb=0.085:aa=1.0")


def curl_json(url):
    out = subprocess.run(['curl', '-sf', '-H', 'User-Agent: %s' % UA, url],
                         capture_output=True, check=True).stdout
    return json.loads(out)


def wiki_lead_image(name):
    q = urllib.parse.quote(name)
    d = curl_json('https://en.wikipedia.org/w/api.php?action=query&titles=%s'
                  '&prop=pageimages&piprop=original|thumbnail&pithumbsize=1400'
                  '&redirects=1&format=json' % q)
    pages = d.get('query', {}).get('pages', {})
    for p in pages.values():
        img = (p.get('thumbnail') or p.get('original') or {}).get('source')
        if img:
            return img, p.get('title', name)
    return None, name


def commons_search(query):
    q = urllib.parse.quote(query)
    d = curl_json('https://commons.wikimedia.org/w/api.php?action=query&generator=search'
                  '&gsrsearch=%s&gsrnamespace=6&gsrlimit=5&prop=imageinfo'
                  '&iiprop=url|mime&iiurlwidth=1400&format=json' % q)
    pages = (d.get('query') or {}).get('pages', {})
    for p in sorted(pages.values(), key=lambda x: x.get('index', 9)):
        info = (p.get('imageinfo') or [{}])[0]
        if info.get('mime') in ('image/jpeg', 'image/png'):
            return info.get('thumburl') or info.get('url'), p.get('title', query)
    return None, query


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    search_mode = '--search' in sys.argv
    duotone = '--no-duotone' not in sys.argv
    name, out = args[0], args[1]
    slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')

    src = None
    # 1. editor-provided image always wins
    for ext in ('png', 'jpg', 'jpeg', 'webp'):
        p = 'assets/people/%s.%s' % (slug, ext)
        if os.path.exists(p):
            src, title = p, '(editor-provided) ' + p
            break
    tmp = '/tmp/fetch-subject-%s' % slug
    if src is None:
        url, title = (commons_search(name) if search_mode else wiki_lead_image(name))
        if url is None and not search_mode:
            url, title = commons_search(name)      # people without pages fall to Commons
        if url is None:
            sys.exit('no image found for %r — drop one at assets/people/%s.png' % (name, slug))
        subprocess.run(['curl', '-sf', '-H', 'User-Agent: %s' % UA, url, '-o', tmp + '.img'], check=True)
        src = tmp + '.img'
        print('source: %s  (%s)' % (title, url))

    cut = tmp + '-cut.png'
    if not os.path.exists(REMBG):
        sys.exit("rembg not found — real imagery / cutouts are the imagery add-on (not part of the core).\n"
                 "Install it:  bash scripts/setup-rembg.sh   (~440MB), then re-run.")
    subprocess.run([REMBG, 'scripts/gen_host_cutout.py', src, cut], check=True)
    if duotone:
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', cut,
                        '-vf', DUO, '-frames:v', '1', out], check=True)
    else:
        subprocess.run(['cp', cut, out], check=True)
    print('wrote %s' % out)


if __name__ == '__main__':
    main()
