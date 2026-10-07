/**
 * Entrée Worker de production (YBW11) — enveloppe l'app Astro générée.
 *
 * Copié dans dist/server/ par le hook `yanbow:workers-dev-redirect`
 * (astro.config.mjs), qui écrit aussi `site-config.mjs` (origine canonique +
 * sources CSP, tirées de src/lib/site.ts et src/lib/subprocessors.ts) et
 * pointe le wrangler.json généré vers ce fichier. La logique est dans
 * `pipeline.mjs` (testée).
 */
// @ts-ignore — généré par l'adaptateur Cloudflare au build
import astro from './entry.mjs';
// @ts-ignore — généré par le hook de build
import * as site from './site-config.mjs';
import { creerWorker } from './pipeline.mjs';

export default creerWorker(astro, site);
