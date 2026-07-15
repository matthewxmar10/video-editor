#!/usr/bin/env node
// link_channel_packs.mjs — makes a CHANNEL's own transition packs discoverable by the engine.
//
// The discovery scan (build_anim_registry.mjs) only reads src/animations/. A channel's packs
// live in Channels/<name>/transitions/<pack>/{long-form,short-form}/index.tsx (see the channel
// READMEs). This step COPIES the active channel's packs into src/animations/<pack>/ just before
// the registry is built, so the plan builder AND the renderer see them — exactly like a base
// pack. It runs on EVERY edit/short render, so switching channels never leaks the last one's
// packs: it first removes every prior channel copy (each is tagged with a .channel-pack marker),
// then copies in the current channel's.
//
//   node scripts/link_channel_packs.mjs --channel "<name>" [--format long-form|short-form]
//   node scripts/link_channel_packs.mjs                      # no channel => just clean up
//
// COPY, not symlink: a pack imports '../_contract' and '../../components/vc/style'. Bundlers
// resolve those against the file's REAL path, so a symlink into src/animations/ would break the
// imports. Copying puts the file physically at src/animations/<pack>/, so its relative imports
// resolve the same way a base pack's do. Author a channel pack's imports as if it sits at
// src/animations/<pack>/ (i.e. '../_contract', '../../components/vc/style') — same as photo/.
import { readdirSync, existsSync, rmSync, mkdirSync, copyFileSync, writeFileSync, statSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = join(HERE, '..');
const ANIM_DIR = join(ROOT, 'src', 'animations');
const MARKER = '.channel-pack';   // a copy's fingerprint: "I was linked in from a channel, delete me next run"

const arg = (flag) => { const i = process.argv.indexOf(flag); return i >= 0 ? process.argv[i + 1] : undefined; };
const channel = arg('--channel') || '';
const format = arg('--format') || 'long-form';
const quiet = process.argv.includes('--quiet');
const log = (...a) => { if (!quiet) console.log(...a); };

// A pack folder can carry helper files next to index.tsx — copy the whole tree.
function copyDir(src, dst) {
  mkdirSync(dst, { recursive: true });
  for (const e of readdirSync(src, { withFileTypes: true })) {
    const s = join(src, e.name), d = join(dst, e.name);
    if (e.isDirectory()) copyDir(s, d);
    else copyFileSync(s, d);
  }
}

// 1) CLEAN — remove every folder we previously copied in (tagged with MARKER). Base/first-party
//    packs (photo, section) have no marker and are never touched.
let cleaned = 0;
for (const e of readdirSync(ANIM_DIR, { withFileTypes: true })) {
  if (!e.isDirectory() || e.name.startsWith('_')) continue;
  if (existsSync(join(ANIM_DIR, e.name, MARKER))) { rmSync(join(ANIM_DIR, e.name), { recursive: true, force: true }); cleaned++; }
}

// 2) No channel (a recording outside Channels/, or an unconfigured one) => cleanup only.
const transitionsDir = channel ? join(ROOT, 'Channels', channel, 'transitions') : '';
if (!channel || !existsSync(transitionsDir)) {
  log(`✓ channel packs: none${cleaned ? ` (cleared ${cleaned} stale)` : ''}${channel ? ` — no Channels/${channel}/transitions/` : ''}`);
  process.exit(0);
}

// 3) COPY IN — each transitions/<pack>/ (skip _template and other _-prefixed), preferring the
//    requested format's index.tsx, falling back to the other so a pack with a single shared
//    (portrait-branching) implementation still links for both formats.
const other = format === 'short-form' ? 'long-form' : 'short-form';
const linked = [];
const skipped = [];
for (const e of readdirSync(transitionsDir, { withFileTypes: true })) {
  if (!e.isDirectory() || e.name.startsWith('_')) continue;
  const pack = e.name;
  const primary = join(transitionsDir, pack, format);
  const fallback = join(transitionsDir, pack, other);
  const srcDir = existsSync(join(primary, 'index.tsx')) ? primary
               : existsSync(join(fallback, 'index.tsx')) ? fallback : '';
  if (!srcDir) { skipped.push(`${pack} (no index.tsx in ${format}/ or ${other}/)`); continue; }

  const dst = join(ANIM_DIR, pack);
  // Never clobber a first-party pack (photo, section, or any hand-written src pack). A channel
  // pack that collides by name is a mistake — surface it instead of silently overwriting.
  if (existsSync(dst) && !existsSync(join(dst, MARKER))) { skipped.push(`${pack} (name collides with a first-party pack in src/animations/)`); continue; }

  copyDir(srcDir, dst);
  writeFileSync(join(dst, MARKER), `channel=${channel}\nformat=${srcDir === primary ? format : other}\nsource=${srcDir.replace(ROOT + '/', '')}\n`);
  linked.push(`${pack}${srcDir === primary ? '' : ` (${other})`}`);
}

log(`✓ channel packs [${channel}, ${format}]: ${linked.length ? linked.join(', ') : 'none'}${cleaned ? `  (cleared ${cleaned} stale)` : ''}`);
for (const s of skipped) log(`  ⚠ skipped ${s}`);
