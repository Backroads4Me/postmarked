// Finds text in .astro templates that relies on a line break for its spacing.
//
// Astro 7 compiles templates with JSX whitespace rules: whitespace containing a
// line break is removed entirely rather than collapsed to a space. So
//
//   use
//   <a href="/x">this link</a>
//   to continue
//
// renders as "usethis linkto continue". Write {' '} where the space matters.
//
// The audit compiles each template twice with Astro's compiler, once with HTML
// whitespace rules and once with JSX rules, and reports every space the JSX
// rules drop between literal text and an inline element or more text. Spaces
// next to block elements, at an element's edge, or between two elements are
// not reported: those only matter outside flex and grid layouts, which the
// compiler cannot see.
//
// Usage: node scripts/whitespace-audit.mjs   (exits 1 when anything is found)

import { createRequire } from 'node:module';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { dirname, join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

const webRoot = join(dirname(fileURLToPath(import.meta.url)), '..');
const require = createRequire(join(webRoot, 'package.json'));
const { transform } = await import(require.resolve('@astrojs/compiler-rs'));

// Inline elements that flow with text. Icons (svg, img) are left out: layouts
// space them with gap or margin, not with a text space.
const INLINE = new Set(
  'a abbr b bdi bdo button cite code data dfn em i kbd label mark q s samp small span strong sub sup time u var'.split(' '),
);

function astroFiles(dir) {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return astroFiles(path);
    return path.endsWith('.astro') ? [path] : [];
  });
}

// Static HTML between ${...} expressions in the compiled $$render`...` templates.
function staticChunks(code) {
  const chunks = [];
  const template = /\$\$render`((?:[^`\\]|\\.)*)`/gs;
  let match;
  while ((match = template.exec(code))) {
    const parts = match[1].split('${');
    chunks.push(parts[0]);
    for (const part of parts.slice(1)) {
      let depth = 1;
      let i = 0;
      for (; i < part.length && depth; i++) {
        if (part[i] === '{') depth++;
        else if (part[i] === '}') depth--;
      }
      chunks.push(part.slice(i));
    }
  }
  return chunks;
}

// What sits beside a dropped space: 'text', 'inline' (element boundary that
// flows with text), or null for anything whose spacing cannot show.
function leftKind(before) {
  if (before === '') return null;
  const tag = before.match(/<(\/?)([a-zA-Z][\w-]*)[^<>]*>$/);
  if (tag) return tag[1] && INLINE.has(tag[2].toLowerCase()) ? 'inline' : null;
  // Any other trailing '>' ends a comment or a tag whose attributes hold an
  // expression, so its start is in an earlier chunk.
  return before.endsWith('>') ? null : 'text';
}

function rightKind(after) {
  if (after === '') return null;
  const tag = after.match(/^<(\/?)([a-zA-Z][\w-]*)/);
  if (tag) return !tag[1] && INLINE.has(tag[2].toLowerCase()) ? 'inline' : null;
  return after.startsWith('<!--') ? null : 'text';
}

function snippet(text, fromEnd) {
  const s = (fromEnd ? text.slice(-30) : text.slice(0, 30)).replace(/\s+/g, ' ');
  return fromEnd ? `…${s}` : `${s}…`;
}

async function compile(source, filename, compact) {
  return staticChunks((await transform(source, { filename, compact })).code);
}

export async function auditTemplates(dir = join(webRoot, 'src')) {
  const findings = [];
  for (const file of astroFiles(dir)) {
    const source = readFileSync(file, 'utf8');
    const html = await compile(source, file, true);
    const jsx = await compile(source, file, 'jsx');
    for (let c = 0; c < Math.min(html.length, jsx.length); c++) {
      const a = html[c];
      const b = jsx[c];
      let i = 0;
      let j = 0;
      while (i < a.length) {
        if (a[i] === b[j]) { i++; j++; continue; }
        if (!/\s/.test(a[i])) break;
        if (/\s/.test(b[j] ?? '')) {
          while (i < a.length && /\s/.test(a[i])) i++;
          while (j < b.length && /\s/.test(b[j])) j++;
          continue;
        }
        const start = i;
        while (i < a.length && /\s/.test(a[i])) i++;
        const before = a.slice(0, start);
        const after = a.slice(i);
        const left = leftKind(before);
        const right = rightKind(after);
        if (left && right && (left === 'text' || right === 'text')) {
          findings.push({ file: relative(webRoot, file), between: `${snippet(before, true)} ⏎ ${snippet(after, false)}` });
        }
      }
    }
  }
  return findings;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const findings = await auditTemplates();
  for (const f of findings) console.log(`${f.file}: ${f.between}`);
  console.log(findings.length ? `\n${findings.length} line break(s) lose their space; add {' '} where it matters.` : 'No whitespace problems found.');
  process.exit(findings.length ? 1 : 0);
}
