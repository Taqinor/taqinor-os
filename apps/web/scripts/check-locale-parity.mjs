/**
 * W313 — CI locale-parity drift guard.
 *
 * For every root path declared translated in `src/i18n/pages.ts`
 * (STATIC_TRANSLATED) plus the CITIES / REALISATIONS dynamic-route templates,
 * asserts that the FR source and its EN/AR mirrors have:
 *   (a) an EQUAL count of <h2>, <h3>, and <section> elements, and
 *   (b) an EQUAL SET of imported `.astro` component basenames (Layout,
 *       Breadcrumb, CtaBand, …) — non-component imports (lib/*.ts, i18n
 *       helpers a locale-prefixed page needs that FR doesn't) are ignored,
 *       since those are expected, structural, non-content asymmetry.
 *
 * Every drift W308–W310 fixed was invisible until a manual file-by-file diff;
 * this script is that diff, automated, so the next FR elevation can't
 * silently outpace its EN/AR mirrors again.
 *
 * Special case — individual blog articles (/blog/<slug>): FR content is
 * markdown (src/content/blog/<slug>.md) rendered through ONE shared template
 * (src/pages/blog/[...slug].astro), while EN/AR ship a per-article static
 * .astro file. This is a genuine architecture difference, not drift, so for
 * these roots: h2/h3 compare markdown `##`/`###` counts against the EN/AR
 * heading tags, <section> is not applicable (skipped), and the component-set
 * check compares EN/AR against the shared FR template's imports.
 *
 * Special case — CITIES / REALISATIONS: served by ONE dynamic-route template
 * per locale (installation-solaire-[city].astro, realisations/[slug].astro),
 * so the template file is compared once per kind rather than per-slug (there
 * is no per-slug source file to compare against).
 *
 * Usage:  node scripts/check-locale-parity.mjs
 * Exit code 0 = no drift found. Exit code 1 = drift found (diff printed).
 *
 * NOTE (out of scope for this task): wiring this into CI (web-build-test) is
 * left for the founder/OS-run — see docs/WEB_PLAN.md W313 `.github` note.
 */
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const ROOT = fileURLToPath(new URL('..', import.meta.url));

const read = (relFromRoot) => readFileSync(path.join(ROOT, relFromRoot), 'utf8');

// ---------------------------------------------------------------------------
// 1. Extract STATIC_TRANSLATED from src/i18n/pages.ts (regex — no TS loader
//    needed for a plain node script; mirrors the array's string literals).
// ---------------------------------------------------------------------------
function extractStaticTranslated() {
  const src = read('src/i18n/pages.ts');
  const match = src.match(/const STATIC_TRANSLATED:[^=]*=\s*\[([\s\S]*?)\n\];/);
  if (!match) {
    throw new Error('Could not locate STATIC_TRANSLATED array in src/i18n/pages.ts');
  }
  // Strip // line comments first — several entries carry French prose
  // comments containing apostrophes (e.g. "l'écart"), which would otherwise
  // be misread as extra string-literal path entries.
  const noComments = match[1]
    .split('\n')
    .map((line) => line.replace(/\/\/[^\r\n]*/, ''))
    .join('\n');
  const paths = [];
  const re = /'([^']*)'/g;
  let m;
  while ((m = re.exec(noComments))) paths.push(m[1]);
  return paths;
}

// ---------------------------------------------------------------------------
// 2. Extract CITIES / REALISATIONS slugs from src/lib/realisations.ts.
//    These are served by ONE dynamic template per locale
//    (installation-solaire-[city].astro / realisations/[slug].astro), so we
//    compare the template file once per kind rather than per-slug (there is
//    no per-slug source file to compare).
// ---------------------------------------------------------------------------
function extractArrayBlock(src, constName) {
  const re = new RegExp(`export const ${constName}[^=]*=\\s*\\[([\\s\\S]*)`);
  const match = src.match(re);
  if (!match) throw new Error(`Could not locate ${constName} in src/lib/realisations.ts`);
  // Find the matching closing "];" at top-level array depth by bracket counting.
  const body = match[1];
  let depth = 1;
  let i = 0;
  for (; i < body.length; i++) {
    if (body[i] === '[') depth++;
    else if (body[i] === ']') {
      depth--;
      if (depth === 0) break;
    }
  }
  return body.slice(0, i);
}

function extractSlugs(constName) {
  const src = read('src/lib/realisations.ts');
  const block = extractArrayBlock(src, constName);
  const slugs = [];
  const re = /slug:\s*'([^']+)'/g;
  let m;
  while ((m = re.exec(block))) slugs.push(m[1]);
  return slugs;
}

// ---------------------------------------------------------------------------
// 3. Resolve a root path -> { fr, en, ar } source file paths (mirrors the
//    srcExists() helper in tests/i18n.test.ts).
// ---------------------------------------------------------------------------
function candidatesFor(root, locale) {
  const base = root === '/' ? 'index' : root.replace(/^\//, '');
  const prefix = locale === 'fr' ? 'src/pages' : `src/pages/${locale}`;
  return [`${prefix}/${base}.astro`, `${prefix}/${base}/index.astro`];
}

function resolveFile(root, locale) {
  for (const c of candidatesFor(root, locale)) {
    if (existsSync(path.join(ROOT, c))) return c;
  }
  return null;
}

// ---------------------------------------------------------------------------
// 4. Structural signals: heading/section counts + imported component set.
// ---------------------------------------------------------------------------
function countTag(src, tag) {
  const re = new RegExp(`<${tag}(?:[\\s>]|$)`, 'g');
  return (src.match(re) ?? []).length;
}

function importedComponents(src) {
  const set = new Set();
  const re = /^import\s+(\w+)\s+from\s+'[^']+\.astro'\s*;?\s*$/gm;
  let m;
  while ((m = re.exec(src))) set.add(m[1]);
  return set;
}

function setDiff(a, b) {
  const onlyA = [...a].filter((x) => !b.has(x));
  const onlyB = [...b].filter((x) => !a.has(x));
  return { onlyA, onlyB };
}

function structuralSignals(fileRel) {
  const src = read(fileRel);
  return {
    h2: countTag(src, 'h2'),
    h3: countTag(src, 'h3'),
    section: countTag(src, 'section'),
    components: importedComponents(src),
  };
}

// Markdown-backed articles (src/content/blog/<slug>.md) count ## / ### as
// their h2/h3 signal — there is no <section> concept in markdown content
// (sections belong to the wrapping template), so that axis is marked N/A.
function markdownHeadingSignals(fileRel) {
  const src = read(fileRel);
  const lines = src.split(/\r?\n/);
  let h2 = 0;
  let h3 = 0;
  for (const line of lines) {
    if (/^###\s/.test(line)) h3++;
    else if (/^##\s/.test(line)) h2++;
  }
  return { h2, h3, section: null, components: null };
}

// ---------------------------------------------------------------------------
// 5. Build the comparison set: STATIC_TRANSLATED roots + one representative
//    root per dynamic-route kind (city template, realisation template) +
//    markdown-article special case (see header doc).
// ---------------------------------------------------------------------------
function blogArticleSlug(root) {
  const m = root.match(/^\/blog\/(.+)$/);
  return m ? m[1] : null;
}

function buildTargets() {
  const staticRoots = extractStaticTranslated();
  const targets = staticRoots.map((root) => {
    const slug = blogArticleSlug(root);
    if (slug && existsSync(path.join(ROOT, `src/content/blog/${slug}.md`))) {
      return {
        kind: 'markdown-article',
        root,
        label: `${root} (markdown-backed article)`,
        mdFile: `src/content/blog/${slug}.md`,
        templateFile: 'src/pages/blog/[...slug].astro',
      };
    }
    return { kind: 'static', root };
  });

  const cities = extractSlugs('CITIES');
  const realisations = extractSlugs('REALISATIONS');

  if (cities.length) {
    targets.push({
      kind: 'dynamic-template',
      root: `/installation-solaire-${cities[0]}`,
      label: `installation-solaire-[city] (dynamic template, ${cities.length} slugs)`,
      // Dynamic route templates use [city] in the filename, not the slug —
      // override candidate resolution below.
      templateBase: 'installation-solaire-[city]',
    });
  }
  if (realisations.length) {
    targets.push({
      kind: 'dynamic-template',
      root: `/realisations/${realisations[0]}`,
      label: `realisations/[slug] (dynamic template, ${realisations.length} slugs)`,
      templateBase: 'realisations/[slug]',
    });
  }
  return targets;
}

function resolveTarget(target, locale) {
  if (target.templateBase) {
    const prefix = locale === 'fr' ? 'src/pages' : `src/pages/${locale}`;
    const f = `${prefix}/${target.templateBase}.astro`;
    return existsSync(path.join(ROOT, f)) ? f : null;
  }
  return resolveFile(target.root, locale);
}

// ---------------------------------------------------------------------------
// 6. Run the comparison.
// ---------------------------------------------------------------------------
function main() {
  const targets = buildTargets();
  const problems = [];

  for (const target of targets) {
    const label = target.label ?? target.root;

    if (target.kind === 'markdown-article') {
      // h2/h3: compare markdown headings to the EN/AR .astro heading tags.
      // <section>: N/A (markdown has no section concept) — skipped.
      // components: compare EN/AR imports against the ONE shared FR template.
      const fr = markdownHeadingSignals(target.mdFile);
      const frTemplateComponents = importedComponents(read(target.templateFile));

      for (const locale of ['en', 'ar']) {
        const file = resolveFile(target.root, locale);
        if (!file) {
          problems.push(`${label}: ${locale.toUpperCase()} source MISSING (checked ${candidatesFor(target.root, locale).join(', ')})`);
          continue;
        }
        const other = structuralSignals(file);

        if (other.h2 !== fr.h2) {
          problems.push(`${label}: h2 count drift — FR(md)=${fr.h2} ${locale.toUpperCase()}=${other.h2} (${target.mdFile} vs ${file})`);
        }
        if (other.h3 !== fr.h3) {
          problems.push(`${label}: h3 count drift — FR(md)=${fr.h3} ${locale.toUpperCase()}=${other.h3} (${target.mdFile} vs ${file})`);
        }
        // <section> intentionally not compared for markdown-backed articles.

        const { onlyA, onlyB } = setDiff(frTemplateComponents, other.components);
        if (onlyA.length || onlyB.length) {
          const parts = [];
          if (onlyA.length) parts.push(`only in FR template: ${onlyA.join(', ')}`);
          if (onlyB.length) parts.push(`only in ${locale.toUpperCase()}: ${onlyB.join(', ')}`);
          problems.push(`${label}: imported component set drift — ${parts.join(' | ')} (${target.templateFile} vs ${file})`);
        }
      }
      continue;
    }

    const frFile = resolveTarget(target, 'fr');
    if (!frFile) {
      problems.push(`${label}: FR source not found (checked ${candidatesFor(target.root, 'fr').join(', ')})`);
      continue;
    }
    const fr = structuralSignals(frFile);

    for (const locale of ['en', 'ar']) {
      const file = resolveTarget(target, locale);
      if (!file) {
        problems.push(`${label}: ${locale.toUpperCase()} source MISSING (checked ${candidatesFor(target.root, locale).join(', ')})`);
        continue;
      }
      const other = structuralSignals(file);

      if (other.h2 !== fr.h2) {
        problems.push(`${label}: h2 count drift — FR=${fr.h2} ${locale.toUpperCase()}=${other.h2} (${frFile} vs ${file})`);
      }
      if (other.h3 !== fr.h3) {
        problems.push(`${label}: h3 count drift — FR=${fr.h3} ${locale.toUpperCase()}=${other.h3} (${frFile} vs ${file})`);
      }
      if (other.section !== fr.section) {
        problems.push(`${label}: <section> count drift — FR=${fr.section} ${locale.toUpperCase()}=${other.section} (${frFile} vs ${file})`);
      }
      const { onlyA, onlyB } = setDiff(fr.components, other.components);
      if (onlyA.length || onlyB.length) {
        const parts = [];
        if (onlyA.length) parts.push(`only in FR: ${onlyA.join(', ')}`);
        if (onlyB.length) parts.push(`only in ${locale.toUpperCase()}: ${onlyB.join(', ')}`);
        problems.push(`${label}: imported component set drift — ${parts.join(' | ')} (${frFile} vs ${file})`);
      }
    }
  }

  if (problems.length) {
    console.error(`\nlocale-parity drift found (${problems.length} issue${problems.length > 1 ? 's' : ''}):\n`);
    for (const p of problems) console.error(`  - ${p}`);
    console.error(`\nChecked ${targets.length} target(s).\n`);
    process.exitCode = 1;
  } else {
    console.log(`locale-parity OK — ${targets.length} target(s) checked, FR/EN/AR structurally aligned.`);
  }
}

main();
