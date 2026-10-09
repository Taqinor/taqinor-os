/**
 * AACQ78 (C-AACQ-074) — GARDE PERMANENTE « enregistré OU lettre morte ».
 *
 * Tout endpoint `src/pages/api/*.ts` qui transmet un lead et répond `ok:true`
 * au visiteur doit avoir, pour ce lead : soit LIVRÉ au CRM (un `fetch` CRM
 * réussi), soit DÉPOSÉ en lettre morte (`kv.put` dans `LEADS_DLQ`, relu
 * ensuite par `resendDeadLetters`), soit ALERTÉ (ligne `[ALERT]`). Sinon le
 * visiteur lit « enregistré » pendant que son lead n'existe nulle part.
 *
 * Trois configurations par endpoint : URL CRM absente, URL faite de blancs,
 * récepteur en 500. Les cas encore fautifs sont GELÉS dans
 * `enregistre-ou-lettre-morte.allow.json` (`<module>:<motif>`), MESURÉS à
 * chaque exécution : la dette ne peut que DÉCROÎTRE — un cas fautif non listé
 * rougit, et une entrée gelée devenue conforme rougit aussi tant qu'elle n'est
 * pas retirée du fichier.
 *
 * Énumération par LECTURE DES IMPORTS : un nouvel endpoint qui importe
 * `forwardLead` (ou le socle `_proxy`) sans être couvert ici fait échouer la
 * garde. Les relais `_proxy` ne déposent pas de lettre morte : la règle qui
 * leur est appliquée est qu'un amont en panne ne produit JAMAIS `ok:true`.
 *
 * Fichier préfixé `_` : Astro ignore les fichiers `_*` de `src/pages` (sinon
 * ce test deviendrait une route du site au build).
 *
 * Seules frontières simulées : `fetch` et la liaison KV.
 */
import { readFileSync, readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mockEnv: Record<string, unknown> = {};
vi.mock('cloudflare:workers', () => ({
  get env() {
    return mockEnv;
  },
  waitUntil: undefined,
}));

import { resetForwardLeadFailureStreak } from '../../lib/lead';
import { resetRateLimit } from '../../lib/rateLimit';
import { resendDeadLetters, resetDeadLetterWarning } from '../../../worker/deadLetter.mjs';

const ICI = fileURLToPath(new URL('.', import.meta.url));
const ALLOW = JSON.parse(readFileSync(fileURLToPath(new URL('./enregistre-ou-lettre-morte.allow.json', import.meta.url)), 'utf-8')) as {
  entrees: string[];
};

const CRM = 'https://crm.example/hook';

/** Lead QUALIFIÉ valide : celui que les trois points d'entrée transmettent. */
const LEAD = {
  fullName: 'Reda K.',
  phone: '0612345678',
  city: 'Casablanca',
  roofType: 'villa',
  billRange: '1500-3000',
  consent: true,
};

type Module = { POST: (ctx: never) => Promise<Response> | Response };

/** Endpoints qui appellent `forwardLead` — imports STATIQUES (vite:dynamic-import-vars). */
const TRANSMETTEURS: Record<string, { charger: () => Promise<Module>; corps: unknown }> = {
  'capture-lead': { charger: () => import('./capture-lead') as Promise<Module>, corps: LEAD },
  'preview-lead': { charger: () => import('./preview-lead') as Promise<Module>, corps: LEAD },
  simulate: { charger: () => import('./simulate') as Promise<Module>, corps: LEAD },
};

/** Relais `_proxy` : un amont en panne ne doit jamais devenir `ok:true`. */
const RELAIS: Record<string, { charger: () => Promise<Module>; corps: unknown }> = {
  'lead-affiner': { charger: () => import('./lead-affiner') as Promise<Module>, corps: { key: 'cle-idem-12345678' } },
  'proposition-option': {
    charger: () => import('./proposition-option') as Promise<Module>,
    corps: { token: 'jeton-proposition-1234', ligne_id: 3 },
  },
};

/** Lecture des imports : quels modules importent `forwardLead` / `_proxy`. */
function enumerer(): { transmetteurs: string[]; relais: string[] } {
  const transmetteurs: string[] = [];
  const relais: string[] = [];
  for (const fichier of readdirSync(ICI)) {
    if (!fichier.endsWith('.ts') || fichier.startsWith('_') || fichier.endsWith('.test.ts')) continue;
    const source = readFileSync(`${ICI}${fichier}`, 'utf-8');
    const nom = fichier.slice(0, -'.ts'.length);
    const imports = source.match(/import[\s\S]*?from\s+['"][^'"]+['"]/g) ?? [];
    if (imports.some((i) => /\bforwardLead\b/.test(i) && /lib\/lead['"]/.test(i))) transmetteurs.push(nom);
    if (imports.some((i) => /from\s+['"]\.\/_proxy['"]/.test(i))) relais.push(nom);
  }
  return { transmetteurs: transmetteurs.sort(), relais: relais.sort() };
}

/** KV en mémoire (frontière) : put/get/list/delete, comptés. */
function kvMemoire() {
  const store = new Map<string, string>();
  const kv = {
    puts: 0,
    async put(key: string, value: string) {
      kv.puts += 1;
      store.set(key, value);
    },
    async get(key: string) {
      return store.get(key) ?? null;
    },
    async list({ prefix = '' }: { prefix?: string; limit?: number } = {}) {
      return { keys: [...store.keys()].filter((k) => k.startsWith(prefix)).map((name) => ({ name })) };
    },
    async delete(key: string) {
      store.delete(key);
    },
  };
  return kv;
}

const CONFIGURATIONS = [
  { nom: 'url-absente', url: undefined as string | undefined, recepteur: 200, motif: 'no-webhook-configured' },
  { nom: 'url-blancs', url: '   ', recepteur: 200, motif: 'no-webhook-configured' },
  { nom: 'recepteur-500', url: CRM, recepteur: 500, motif: 'webhook-status-500' },
] as const;

type Mesure = { ok: boolean; crmLivre: number; puts: number; alertes: number; kv: ReturnType<typeof kvMemoire> };

async function mesurer(nom: string, config: (typeof CONFIGURATIONS)[number]): Promise<Mesure> {
  resetRateLimit();
  resetForwardLeadFailureStreak();
  resetDeadLetterWarning();
  for (const k of Object.keys(mockEnv)) delete mockEnv[k];
  const kv = kvMemoire();
  mockEnv.LEADS_DLQ = kv;
  mockEnv.LEAD_WEBHOOK_SECRET = 's3cret';
  if (config.url !== undefined) mockEnv.LEAD_WEBHOOK_URL = config.url;
  let crmLivre = 0;
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      if (String(url) === CRM) {
        if (config.recepteur < 300) crmLivre += 1;
        return { ok: config.recepteur < 300, status: config.recepteur, json: async () => ({}) } as unknown as Response;
      }
      throw new TypeError('réseau coupé (simulateur / CAPI hors périmètre)');
    }),
  );
  // Les réessais de `forwardLead` (1 s puis 3 s) passent sans attendre.
  vi.stubGlobal('setTimeout', ((fn: () => void) => {
    fn();
    return 0;
  }) as unknown as typeof setTimeout);
  let alertes = 0;
  const erreur = vi.spyOn(console, 'error').mockImplementation((...args: unknown[]) => {
    if (args.some((a) => String(a).includes('[ALERT]'))) alertes += 1;
  });
  vi.spyOn(console, 'log').mockImplementation(() => {});
  vi.spyOn(console, 'warn').mockImplementation(() => {});
  const mod = await TRANSMETTEURS[nom].charger();
  const res = await mod.POST({
    request: new Request(`http://localhost/api/${nom}`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(TRANSMETTEURS[nom].corps),
    }),
  } as never);
  const json = (await res.json()) as Record<string, unknown>;
  erreur.mockRestore();
  return { ok: res.status === 200 && json.ok === true, crmLivre, puts: kv.puts, alertes, kv };
}

const conforme = (m: Mesure): boolean => !m.ok || m.crmLivre > 0 || m.puts > 0 || m.alertes > 0;

describe('AACQ78 — « enregistré » veut dire livré, en lettre morte ou alerté', () => {
  beforeEach(() => {
    resetRateLimit();
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('l’énumération par les imports est exactement l’ensemble couvert (un nouvel endpoint rougit)', () => {
    const { transmetteurs, relais } = enumerer();
    expect(transmetteurs.length).toBeGreaterThan(0);
    expect(transmetteurs).toEqual(Object.keys(TRANSMETTEURS).sort());
    expect(relais).toEqual(Object.keys(RELAIS).sort());
  });

  it('la dette gelée est EXACTEMENT l’ensemble des cas fautifs mesurés (décroissance seulement)', async () => {
    const fautifs = new Set<string>();
    for (const nom of Object.keys(TRANSMETTEURS)) {
      for (const config of CONFIGURATIONS) {
        const m = await mesurer(nom, config);
        if (!conforme(m)) fautifs.add(`${nom}:${config.motif}`);
      }
    }
    const gelees = new Set(ALLOW.entrees);
    const nonGeles = [...fautifs].filter((c) => !gelees.has(c)).sort();
    const devenuesConformes = [...gelees].filter((c) => !fautifs.has(c)).sort();
    expect(nonGeles, `ok:true sans livraison, lettre morte ni alerte : ${nonGeles.join(', ')}`).toEqual([]);
    expect(
      devenuesConformes,
      `entrée(s) gelée(s) désormais conforme(s) — la retirer de enregistre-ou-lettre-morte.allow.json : ${devenuesConformes.join(', ')}`,
    ).toEqual([]);
  });

  it('récepteur en 500 : le lead dort en lettre morte puis est LIVRÉ par resendDeadLetters', async () => {
    for (const nom of Object.keys(TRANSMETTEURS)) {
      const config = CONFIGURATIONS.find((c) => c.nom === 'recepteur-500')!;
      const m = await mesurer(nom, config);
      expect(m.ok, nom).toBe(true);
      expect(m.puts, `${nom} : aucun dépôt en lettre morte`).toBeGreaterThanOrEqual(1);
      vi.unstubAllGlobals();
      const livres: string[] = [];
      const fetchRetabli = vi.fn(async (url: string) => {
        livres.push(String(url));
        return { ok: true, status: 200 } as unknown as Response;
      });
      const bilan = await resendDeadLetters({ LEADS_DLQ: m.kv, LEAD_WEBHOOK_URL: CRM }, fetchRetabli as unknown as typeof fetch, () => {});
      expect(bilan.found, nom).toBeGreaterThanOrEqual(1);
      expect(bilan.delivered, nom).toBeGreaterThanOrEqual(1);
      expect(livres, nom).toContain(CRM);
    }
  });

  it('relais `_proxy` : un amont en panne (500 ou injoignable) ne répond jamais ok:true', async () => {
    for (const [nom, relais] of Object.entries(RELAIS)) {
      for (const panne of ['500', 'injoignable'] as const) {
        resetRateLimit();
        vi.stubGlobal(
          'fetch',
          vi.fn(async () => {
            if (panne === 'injoignable') throw new TypeError('réseau coupé');
            return { ok: false, status: 500, json: async () => ({}) } as unknown as Response;
          }),
        );
        const mod = await relais.charger();
        const res = await mod.POST({
          request: new Request(`http://localhost/api/${nom}`, {
            method: 'POST',
            headers: { 'content-type': 'application/json' },
            body: JSON.stringify(relais.corps),
          }),
        } as never);
        const json = (await res.json()) as Record<string, unknown>;
        expect(json.ok, `${nom} (${panne})`).not.toBe(true);
        vi.unstubAllGlobals();
      }
    }
  });

  it('la liste gelée ne nomme que des modules couverts et des motifs mesurés', () => {
    const motifs = new Set(CONFIGURATIONS.map((c) => c.motif));
    for (const entree of ALLOW.entrees) {
      const [module, motif] = entree.split(':');
      expect(Object.keys(TRANSMETTEURS), entree).toContain(module);
      expect([...motifs], entree).toContain(motif);
    }
  });
});
