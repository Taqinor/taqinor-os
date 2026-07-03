#!/usr/bin/env node
/**
 * W323 — CI Lighthouse gate over the pages that matter.
 *
 * « Lighthouse 97–100 » is written into nearly every task's acceptance
 * criteria across docs/WEB_PLAN.md, but until this task it was an
 * UNENFORCED aspiration measured by hand on 7 FR pages
 * (scripts/lighthouse-all.ps1, no thresholds, no CI). This script is the
 * enforcement layer: it audits the routes in scripts/lighthouse.config.mjs,
 * asserts the 97–100 floor on all four categories, AND — for the two
 * journey pages whose meaningful content is gated behind an async step
 * (the capture map on /devis/mon-toit, the savings/production chart on
 * /proposition/[token]) — asserts that the EXPECTED element is what
 * Lighthouse actually reports as the LCP node. A score alone can pass while
 * a loading skeleton or a stale hero image is what actually painted first;
 * this closes that gap.
 *
 * USAGE (local, standalone — no CI wiring required to run it yourself):
 *   1. Build + serve the site however you like (e.g. `npm run build` then
 *      serve apps/web/dist/client with any static server, or point
 *      --base-url at a running `npm run dev`).
 *   2. node scripts/lighthouse-gate.mjs --base-url=http://127.0.0.1:4321
 *
 * ENV:
 *   BASE_URL                      — same as --base-url, env takes the flag's place if unset.
 *   LIGHTHOUSE_PROPOSITION_TOKEN  — a REAL seeded devis/proposal token for the
 *                                    /proposition/[token] route. Without it, that ONE route
 *                                    is SKIPPED with a clear warning — never audited against
 *                                    a fabricated token or a bare 404.
 *   CHROME_PATH                   — passed straight to chrome-launcher (matches
 *                                    scripts/lighthouse-all.ps1's existing convention).
 *
 * EXIT CODE: non-zero if any audited route fails the floor or (on the two
 * gated pages) reports the wrong LCP element — so this is a valid CI gate
 * step as soon as it's wired into a job that serves the build first (see the
 * WIRING NOTE in scripts/lighthouse.config.mjs — that wiring is OUT OF SCOPE
 * here: this task only ships the config + script under apps/web/).
 */
import { launch } from 'chrome-launcher';
import lighthouse from 'lighthouse';
import { CATEGORIES, ROUTES, SCORE_FLOOR } from './lighthouse.config.mjs';

function parseArgs(argv) {
  const out = {};
  for (const arg of argv) {
    const m = /^--([\w-]+)=(.*)$/.exec(arg);
    if (m) out[m[1]] = m[2];
  }
  return out;
}

async function auditRoute(baseUrl, route, chromePort) {
  const token = route.envToken ? process.env[route.envToken] : undefined;
  if (route.seeded && !token) {
    return { route, skipped: true, reason: `no ${route.envToken} set — provide a real seeded token to audit this route` };
  }
  const path = typeof route.path === 'function' ? route.path(token) : route.path;
  const url = new URL(path, baseUrl).href;

  const result = await lighthouse(
    url,
    {
      port: chromePort,
      output: 'json',
      onlyCategories: CATEGORIES,
      logLevel: 'error',
    },
  );

  const lhr = result.lhr;
  const scores = Object.fromEntries(
    CATEGORIES.map((c) => [c, Math.round((lhr.categories[c]?.score ?? 0) * 100)]),
  );
  const failures = CATEGORIES.filter((c) => scores[c] < SCORE_FLOOR);

  let lcpCheck;
  if (route.lcpSelector) {
    // The LCP element node is reported inside the 'lcp-breakdown-insight'
    // audit's details (a `type: 'list'` whose items include a nested
    // `type: 'table'` breakdown AND a `type: 'node'` item carrying the DOM
    // node Lighthouse identified as LCP, with a DevTools-style `selector`
    // string, e.g. "body > main#mt-stage" — verified against Lighthouse
    // 13's actual output shape (older Lighthouse versions exposed this under
    // a separate 'largest-contentful-paint-element' audit; both are checked
    // here so this keeps working across a Lighthouse upgrade). We check the
    // expected selector's tag is a SUBSTRING of the reported selector —
    // robust to Lighthouse formatting the path with ancestor nodes.
    const candidateAudits = [
      lhr.audits['largest-contentful-paint-element'], // older Lighthouse shape
      lhr.audits['lcp-breakdown-insight'], // Lighthouse 12+ "insight" shape
    ].filter(Boolean);
    const allItems = candidateAudits.flatMap((a) => a.details?.items ?? []);
    const nodeItem = allItems
      .flatMap((i) => (i?.type === 'node' ? [i] : (i?.items ?? [])))
      .find((i) => i?.type === 'node' || i?.node);
    const reportedSelector = nodeItem?.selector ?? nodeItem?.node?.selector ?? '';
    const matches = reportedSelector.includes(route.lcpSelector.replace(/^[.#]/, ''));
    lcpCheck = { expected: route.lcpSelector, reported: reportedSelector, matches };
  }

  return { route, scores, failures, lcpCheck, skipped: false };
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const baseUrl = args['base-url'] ?? process.env.BASE_URL ?? 'http://127.0.0.1:4321';

  const chrome = await launch({
    chromeFlags: ['--headless=new', '--disable-gpu', '--no-sandbox'],
  });

  const results = [];
  try {
    for (const route of ROUTES) {
      process.stderr.write(`Auditing ${route.name}...\n`);
      // eslint-disable-next-line no-await-in-loop
      const res = await auditRoute(baseUrl, route, chrome.port);
      results.push(res);
    }
  } finally {
    // Chrome's tmp-profile cleanup can fail on Windows with a transient
    // EPERM (file still briefly locked) — never let that mask the actual
    // audit results below; the gate's exit code must reflect the SCORES,
    // not an unrelated OS file-lock race during teardown.
    try {
      await chrome.kill();
    } catch (killErr) {
      process.stderr.write(`(non-fatal) chrome teardown warning: ${killErr?.message ?? killErr}\n`);
    }
  }

  let ok = true;
  for (const r of results) {
    if (r.skipped) {
      process.stdout.write(`SKIP  ${r.route.name} — ${r.reason}\n`);
      continue;
    }
    const line = CATEGORIES.map((c) => `${c} ${r.scores[c]}`).join('  ');
    const pass = r.failures.length === 0 && (!r.lcpCheck || r.lcpCheck.matches);
    if (!pass) ok = false;
    process.stdout.write(`${pass ? 'PASS' : 'FAIL'}  ${r.route.name.padEnd(20)} ${line}\n`);
    if (r.failures.length) {
      process.stdout.write(`      below floor (${SCORE_FLOOR}): ${r.failures.join(', ')}\n`);
    }
    if (r.lcpCheck && !r.lcpCheck.matches) {
      process.stdout.write(
        `      LCP element mismatch: expected "${r.lcpCheck.expected}", Lighthouse reported "${r.lcpCheck.reported}"\n`,
      );
    }
  }

  if (!ok) {
    process.stderr.write('\nLighthouse gate FAILED.\n');
    process.exitCode = 1;
  } else {
    process.stderr.write('\nLighthouse gate passed.\n');
  }
}

main().catch((err) => {
  process.stderr.write(`${err?.stack ?? err}\n`);
  process.exitCode = 1;
});
