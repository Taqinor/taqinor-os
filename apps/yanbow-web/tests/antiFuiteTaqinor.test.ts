/**
 * YBW56 — garde anti-fuite : le site YanBow n'envoie JAMAIS vers la société
 * de l'entreprise d'installation. Le récepteur `webhooks/website-leads/` de
 * l'ERP retombe sur la PREMIÈRE société et lance un devis solaire : un site qui
 * l'utiliserait atterrirait chez elle. Échoue si le site (source ET build)
 * contient ce chemin, ses réglages (`LEAD_WEBHOOK_*`, `WEBSITE_LEADS_COMPANY_ID`)
 * ou importe quoi que ce soit depuis `apps/web`.
 */
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const RACINE = fileURLToPath(new URL('../', import.meta.url));

/** Motifs interdits, nommés. */
export const INTERDITS: { nom: string; motif: RegExp }[] = [
  { nom: 'récepteur website-leads', motif: /webhooks\/website-leads/ },
  { nom: 'variables LEAD_WEBHOOK_*', motif: /LEAD_WEBHOOK_/ },
  { nom: 'WEBSITE_LEADS_COMPANY_ID', motif: /WEBSITE_LEADS_COMPANY_ID/ },
  { nom: 'import depuis apps/web', motif: /(?:\bfrom\s*|\bimport\s*\(?\s*|\brequire\(\s*)['"][^'"]*(?:apps\/web\/|(?:\.\.\/)+web\/)/ },
];

/** Dossiers jamais lus : dépendances, et les tests (ils citent les motifs pour les prouver). */
const IGNORES = new Set(['node_modules', 'tests', 'tests-e2e', 'test-results', '.astro', '.wrangler', '.git']);
const EXTENSIONS = /\.(m?[jt]s|astro|json|jsonc|html|css|md|txt|example|toml|yml|yaml)$|^\.dev\.vars/;

function fichiers(dir: string): string[] {
  return readdirSync(dir).flatMap((n) => {
    if (IGNORES.has(n)) return [];
    const p = join(dir, n);
    if (statSync(p).isDirectory()) return fichiers(p);
    return EXTENSIONS.test(n) ? [p] : [];
  });
}

/** Fuites trouvées : `chemin : motif`. */
export function fuites(entrees: { rel: string; contenu: string }[]): string[] {
  return entrees.flatMap((e) => INTERDITS.filter((i) => i.motif.test(e.contenu)).map((i) => `${e.rel} : ${i.nom}`));
}

describe('YBW56 — garde anti-fuite vers la société de l’entreprise d’installation', () => {
  it('cas négatifs : chaque motif planté est détecté', () => {
    const pieges = [
      { rel: 'src/a.ts', contenu: "fetch('https://api.exemple/api/django/crm/webhooks/website-leads/')" },
      { rel: 'src/b.ts', contenu: 'const u = env.LEAD_WEBHOOK_URL;' },
      { rel: '.dev.vars.example', contenu: 'WEBSITE_LEADS_COMPANY_ID=1' },
      { rel: 'src/c.ts', contenu: "import { forwardLead } from '../../../web/src/lib/lead';" },
      { rel: 'src/d.ts', contenu: "const m = await import('apps/web/src/lib/lead');" },
    ];
    expect(fuites(pieges)).toEqual([
      'src/a.ts : récepteur website-leads',
      'src/b.ts : variables LEAD_WEBHOOK_*',
      '.dev.vars.example : WEBSITE_LEADS_COMPANY_ID',
      'src/c.ts : import depuis apps/web',
      'src/d.ts : import depuis apps/web',
    ]);
    expect(fuites([{ rel: 'src/ok.ts', contenu: "const u = env.YANBOW_RDV_URL; import x from '../lib/web-ok';" }])).toEqual([]);
  });

  it('source du site (src, worker, scripts, public, configuration) : aucune fuite', () => {
    const entrees = fichiers(RACINE)
      .filter((p) => !relative(RACINE, p).split(sep).includes('dist'))
      .map((p) => ({ rel: relative(RACINE, p).split(sep).join('/'), contenu: readFileSync(p, 'utf-8') }));
    expect(entrees.length).toBeGreaterThan(20);
    expect(fuites(entrees)).toEqual([]);
  });

  it('build (dist/ : HTML, scripts client, Worker) : aucune fuite', () => {
    const dist = join(RACINE, 'dist');
    if (!existsSync(dist)) throw new Error('dist/ absent — lancer `npm run build` avant `npm test`');
    const entrees = fichiers(dist).map((p) => ({ rel: relative(RACINE, p).split(sep).join('/'), contenu: readFileSync(p, 'utf-8') }));
    expect(entrees.some((e) => e.rel.startsWith('dist/server/'))).toBe(true);
    expect(fuites(entrees)).toEqual([]);
  });
});
