// W323 — CI Lighthouse gate config: the pages that matter + the 97–100 floor
// + the LCP element identity check on the two journey pages.
//
// « Lighthouse 97–100 » is written into nearly every task's acceptance
// criteria across this plan, but until this task it was an UNENFORCED
// aspiration measured by hand (see scripts/lighthouse-all.ps1, a 7-FR-page
// manual tool with no thresholds/CI wiring). This config is the single
// source of truth the gate script reads — categories, floor, routes, and
// the LCP selector expected on the two map/chart-gated journey pages (a
// score alone can pass while the ACTUAL meaningful content lags behind a
// map-init or chart-JS gate — see scripts/lighthouse-gate.mjs).
//
// WIRING NOTE (out of scope for this task, per the web-plan run rules — CI
// workflow edits are `.github/**`, outside `apps/web`): the founder/OS-run
// must add a step to the `web-build-test` job that runs
//   node apps/web/scripts/lighthouse-gate.mjs
// against a built+served `apps/web/dist` (or preview server) before this
// gate does anything in CI. Locally it already runs standalone — see the
// README block at the top of lighthouse-gate.mjs.

/** The 97–100 floor applied to every category, on every route below. */
export const SCORE_FLOOR = 97;

/** Lighthouse categories scored (same four scripts/lighthouse-all.ps1 already reports). */
export const CATEGORIES = ['performance', 'accessibility', 'best-practices', 'seo'];

/**
 * Routes audited. `path` is resolved against the gate's `--base-url` (default
 * http://127.0.0.1:4321, Astro's own preview port) or the env BASE_URL.
 *
 * `lcpSelector` (only on the two journey pages, per the task): a CSS selector
 * the gate additionally asserts is the LCP element reported in the trace —
 * NOT just that the performance score cleared the floor. These two pages
 * gate their most meaningful content behind an async step (map init /
 * chart JS), so a stale hero image or a loading skeleton can technically
 * "score" 97+ while the real content the visitor came for hasn't painted —
 * exactly the blind spot the task calls out.
 */
export const ROUTES = [
  { name: 'home', path: '/' },
  {
    name: 'devis-mon-toit',
    path: '/devis/mon-toit',
    // Map-init-gated: `#mt-stage` (src/pages/devis/mon-toit.astro) wraps the
    // whole address-search + map interaction area — the meaningful content
    // once a visitor reaches the map step. Asserted against this stable
    // page-level container (not the inner #rp9-map, which only exists after
    // the map script boots) so the check survives internal step churn.
    lcpSelector: '#mt-stage',
  },
  {
    name: 'proposition-token',
    // Seeded per the task ("/proposition/[token] (seeded)"): this route
    // reads a REAL backend record by token (src/pages/proposition/[token].astro
    // → PUBLIC_API_BASE). No fake data is ever injected here. Provide a real
    // seeded token via the LIGHTHOUSE_PROPOSITION_TOKEN env var when a test
    // fixture/backend exists (see lighthouse-gate.mjs); until then the gate
    // SKIPS this route with a clear warning rather than auditing a 404 or
    // fabricating content.
    path: (token) => `/proposition/${token}`,
    seeded: true,
    envToken: 'LIGHTHOUSE_PROPOSITION_TOKEN',
    // Chart-JS-gated: `.chart-svg` (src/pages/proposition/[token].astro,
    // rendered by lib/proposalChart.ts) is the savings/production chart —
    // the meaningful content once the proposal has loaded, as opposed to a
    // loading skeleton that could otherwise still score well.
    lcpSelector: '.chart-svg',
  },
  { name: 'en-home', path: '/en/' },
  { name: 'ar-home', path: '/ar/' },
];
