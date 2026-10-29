// @vitest-environment jsdom
//
// RWEB17 (filet) — HARNESS D'EXÉCUTION du tunnel « mon-toit » dans les TROIS locales.
//
// POURQUOI. Avant ce fichier, AUCUN test n'exécutait le <script> des pages
// `src/pages/devis/mon-toit.astro`, `src/pages/en/devis/mon-toit.astro`,
// `src/pages/ar/devis/mon-toit.astro` : les gardes du tunnel lisent la SOURCE
// `.astro` (regex) ou appellent `construireCorps` (lib/tunnel, partagé) sur un
// état fabriqué — elles ne voient donc pas le câblage PROPRE à chaque page
// (syncStep2Panels, syncModeCards, wireCardGroup, computeEstimate,
// saveWizardState, markDataEntered, les ~47 `let` de haut niveau…). Le
// refactor RWEB17 (dédoublonnage des trois scripts) DOIT garder ce fichier vert.
//
// CE QUI TOURNE. Le VRAI artefact livré : le HTML construit
// (`dist/client/<route>/index.html`, via builtHtmlHelper) et le chunk JS que la
// page charge (`/_astro/mon-toit.astro_astro_type_script_index_0_lang.*.js`,
// lu dans la balise <script src> de CE HTML — jamais un nom deviné). Le DOM est
// monté dans jsdom, les autres scripts (Layout, compteur…) sont retirés, puis le
// chunk est importé (il s'exécute à l'import, exactement comme dans le
// navigateur). On pilote ensuite le parcours au clic/à la saisie jusqu'à
// l'envoi du formulaire, et on enregistre le corps EXACT du POST
// `/api/capture-lead` (la page utilise `fetch` ; `sendBeacon` ne sert qu'à la
// balise de funnel, enregistrée à part et jamais comparée).
//
// DÉTERMINISME. Aucune requête réseau : `fetch` est un bouchon
// (`/api/roof-config` → carte indisponible → repli adresse, donc ni MapLibre ni
// Three.js ; `/api/capture-lead` → `{ ok: true, qualified: true }` ;
// `/api/lead-ref-lookup` → `{ ok: false }`). Les estimations sont calculées par
// les moteurs LOCAUX (billEstimate/estimatorPro/estimatorAgricole — aucun appel
// PVGIS depuis cette page). Date figée (`Date` seul simulé), `Math.random`
// semé, `crypto.randomUUID` compté, `prefers-reduced-motion` vrai (délai de
// « calcul » = 0). Les jetons à usage unique (`idempotencyKey`, `eventId`,
// `clientRef`, `appareilId`) sont vérifiés sur leur FORME puis
// remplacés par un marqueur avant comparaison.
//
// LES GOLDENS. `tests/__snapshots__/tunnelExecution/<parcours>.<locale>.json`
// (un par parcours × locale). Puis une assertion CROISÉE : FR, EN et AR
// produisent le MÊME corps, à l'exception des seules clés listées dans
// `CLES_PROPRES_A_LA_LOCALE` (avec leur valeur attendue par locale).
//
// LANCER.
//   cd apps/web && npm run build && npx vitest run tests/tunnelExecution.test.ts
// (le job CI `web-build-test` fait `npm run build` avant `npm test`). Lecture du
// HTML : même contrat que tests/builtHtmlHelper.ts (inutilisable sous jsdom). Régénérer
// un golden après un changement VOULU du corps :
//   npx vitest run tests/tunnelExecution.test.ts -u   — puis relire le diff.
import { existsSync, readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

type Locale = 'fr' | 'en' | 'ar';
const ROUTES: Record<Locale, string> = { fr: '/devis/mon-toit', en: '/en/devis/mon-toit', ar: '/ar/devis/mon-toit' };
const LOCALES: Locale[] = ['fr', 'en', 'ar'];
// `new URL(…, import.meta.url)` est la classe URL de jsdom ici (refusée par
// fileURLToPath) : chemin calculé à partir de la chaîne `import.meta.url`.
const DIST = join(dirname(fileURLToPath(import.meta.url)), '..', 'dist', 'client') + '/';

/** HTML construit d'une route — même contrat que builtHtmlHelper.builtPage (dist absent = ÉCHEC). */
function builtPage(route: string): string {
  const file = join(DIST, route.replace(/^\/+|\/+$/g, ''), 'index.html');
  if (!existsSync(file)) throw new Error(`HTML construit introuvable : ${file} — lancer « npm run build » avant vitest.`);
  return readFileSync(file, 'utf-8');
}

/**
 * Les SEULES clés du corps autorisées à différer entre locales, avec la valeur
 * attendue dans chacune (`undefined` = clé absente). Tout autre écart = rouge.
 * `langue_preferee` : FR/AR transmettent la langue affichée ; EN n'envoie rien
 * (`LEAD_LANGS` n'accepte que fr/ar — cf. src/lib/tunnel/champs.ts).
 */
const CLES_PROPRES_A_LA_LOCALE: Record<string, Record<Locale, unknown>> = {
  langue_preferee: { fr: 'fr', en: undefined, ar: 'ar' },
};

/**
 * WEBERR-TUNNEL-PAYBACK-FR — sous-clés de `estimateShown` dont le TEXTE suit la
 * langue de la page (le conseiller CRM lit ce que le client a lu). Comparées à
 * part (forme attendue par locale, quand la clé est présente), puis retirées de
 * la comparaison croisée — tous les CHIFFRES restent identiques entre locales.
 */
const SOUS_CLES_ESTIMATION_PROPRES_A_LA_LOCALE: Record<string, Record<Locale, RegExp>> = {
  paybackLabel: { fr: /^\d+ à \d+ ans$/, en: /^\d+ – \d+ years$/, ar: /^\d+ – \d+ سنة$/ },
};

/** Jetons à usage unique : forme vérifiée, puis valeur masquée. */
const JETONS: Record<string, RegExp> = {
  idempotencyKey: /^[A-Za-z0-9_-]{8,64}$/,
  eventId: /^[A-Za-z0-9_-]{8,64}$/,
  clientRef: /^TQ-[A-Z0-9]{4,}$/,
  appareilId: /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/,
};

// ── le parcours : une suite d'actions rejouée à l'identique dans chaque locale ──
type Action =
  | { clic: string }
  | { saisir: string; valeur: string }
  | { choisir: string; valeur: string }
  | { cocher: string }
  | { attendre: true }
  | { envoyer: true };

const CONTACT: Action[] = [
  { saisir: '#mt-name', valeur: 'Karim Benali' },
  { saisir: '#mt-phone', valeur: '0612345678' },
  { saisir: '#mt-city', valeur: 'Casablanca, Maarif' },
  { saisir: '#mt-email', valeur: 'karim@example.com' },
  { cocher: '#mt-consent' },
  { envoyer: true },
];

const PARCOURS: Record<string, Action[]> = {
  // Résidentiel, montant exact + journée type + équipement VE + préférence « appelez-moi ».
  residentiel: [
    { clic: '.mt-mode[data-mode="residentiel"]' },
    { clic: '#mt-next-0' },
    { saisir: '#mt-facture-hiver', valeur: '1800' },
    { clic: '.mt-occ-btn[data-occ-id="presence_jour"]' },
    { cocher: '#mt-equip-ve' },
    { saisir: '#mt-equip-ve-km', valeur: '250' },
    { clic: '#mt-estimate' },
    { attendre: true },
    { cocher: '#mt-contact-phone' },
    ...CONTACT,
  ],
  // Résidentiel, tranche seule (aucun montant exact).
  residentiel_tranche: [
    { clic: '.mt-mode[data-mode="residentiel"]' },
    { clic: '#mt-next-0' },
    { choisir: '#mt-bill', valeur: '1500-3000' },
    { clic: '#mt-estimate' },
    { attendre: true },
    ...CONTACT,
  ],
  // Industriel : conso MAD, moyenne tension, 24/7, 3×8, toiture-terrasse + surface, raison sociale.
  industriel: [
    { clic: '.mt-mode[data-mode="industriel"]' },
    { clic: '#mt-next-0' },
    { saisir: '#mt-pro-bill', valeur: '42000' },
    { clic: '.mt-tension[data-value="mt"]' },
    { clic: '.mt-activity[data-value="continuous"]' },
    { clic: '.mt-equipes[data-value="3x8"]' },
    { clic: '.mt-surface-type[data-value="terrasse"]' },
    { saisir: '#mt-surface-m2', valeur: '900' },
    { clic: '#mt-estimate' },
    { attendre: true },
    { saisir: '#mt-raison-sociale', valeur: 'Atlas Plast SARL' },
    ...CONTACT,
  ],
  // Commercial : 1re catégorie rendue, facture en kWh.
  commercial: [
    { clic: '.mt-mode[data-mode="commercial"]' },
    { clic: '#mt-next-0' },
    { clic: '.mt-commercial-cat' },
    { clic: '.mt-cc-unit[data-value="kwh"]' },
    { saisir: '#mt-cc-bill', valeur: '9000' },
    { clic: '#mt-estimate' },
    { attendre: true },
    { saisir: '#mt-raison-sociale', valeur: 'Hôtel Les Palmiers' },
    ...CONTACT,
  ],
  // Agricole : forage, hydraulique, culture + région (1res cartes), heures touchées, carburant.
  agricole: [
    { clic: '.mt-mode[data-mode="agricole"]' },
    { clic: '#mt-next-0' },
    { clic: '.mt-water-source[data-value="forage"]' },
    { saisir: '#mt-profondeur', valeur: '60' },
    { saisir: '#mt-hmt', valeur: '85' },
    { saisir: '#mt-water-need', valeur: '30' },
    { clic: '.mt-culture-card' },
    { clic: '.mt-region-card' },
    { saisir: '#mt-heures-pompage', valeur: '9' },
    { saisir: '#mt-surface-ha', valeur: '4' },
    { saisir: '#mt-fuel-spend', valeur: '2500' },
    { clic: '#mt-estimate' },
    { attendre: true },
    ...CONTACT,
  ],
};

/** État du navigateur AVANT le chargement de la page, par parcours : le
 *  parcours résidentiel complet arrive avec le consentement mesure accordé
 *  (→ `appareilId` émis) et une attribution first-touch (→ fbclid/UTM). */
const AVANT_CHARGEMENT: Record<string, { local?: Record<string, string>; session?: Record<string, string> }> = {
  residentiel: {
    local: { tq_consent: 'granted' },
    session: { tq_fbclid: 'fb.1.123', tq_utm_source: 'facebook', tq_utm_campaign: 'toit-casa' },
  },
};

// ── montage ──────────────────────────────────────────────────────────────────
function chunkDeLaPage(html: string): string {
  const m = html.match(/<script type="module" src="\/(_astro\/mon-toit\.astro_astro_type_script_index_0_lang\.[^"]+\.js)">/);
  if (!m) throw new Error('chunk du script mon-toit introuvable dans le HTML construit');
  const chemin = `${DIST}${m[1]}`;
  if (!existsSync(chemin)) throw new Error(`chunk introuvable : ${chemin}`);
  return chemin;
}

/** Monte le HTML construit dans le document jsdom, scripts retirés. */
function monterDom(html: string, route: string) {
  const htmlTag = html.match(/<html([^>]*)>/)?.[1] ?? '';
  const interieur = html.slice(html.indexOf('>', html.indexOf('<html')) + 1, html.lastIndexOf('</html>'));
  document.documentElement.innerHTML = interieur.replace(/<script\b[\s\S]*?<\/script>/g, '');
  for (const a of ['lang', 'dir']) {
    const v = htmlTag.match(new RegExp(`${a}="([^"]*)"`))?.[1];
    if (v) document.documentElement.setAttribute(a, v);
    else document.documentElement.removeAttribute(a);
  }
  window.history.replaceState(null, '', route);
}

interface Enregistrement { lead: Record<string, unknown>[]; autres: string[]; balises: string[] }

function bouchonner(): Enregistrement {
  const rec: Enregistrement = { lead: [], autres: [], balises: [] };
  const repondre = (body: unknown) => Promise.resolve(new Response(JSON.stringify(body), { status: 200, headers: { 'content-type': 'application/json' } }));
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url.startsWith('/api/capture-lead')) {
      rec.lead.push(JSON.parse(String(init?.body ?? '{}')));
      return repondre({ ok: true, qualified: true });
    }
    rec.autres.push(url);
    if (url.startsWith('/api/roof-config')) return repondre({ available: false });
    return repondre({ ok: false });
  }));
  // RWEB17-M9 — les balises de funnel sont désormais LUES (suite ordonnée), jeton de session masqué.
  Object.defineProperty(navigator, 'sendBeacon', {
    configurable: true,
    value: (_url: string, blob: Blob) => {
      const i = rec.balises.length;
      rec.balises.push('');
      const lecteur = new FileReader();
      lecteur.onload = () => {
        const p = JSON.parse(String(lecteur.result)) as { step: string; action: string; path: string };
        rec.balises[i] = `${p.step}:${p.action} ${p.path}`;
      };
      lecteur.readAsText(blob);
      return true;
    },
  });
  window.matchMedia = ((q: string) => ({
    matches: q.includes('prefers-reduced-motion'), media: q, onchange: null,
    addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {}, dispatchEvent: () => false,
  })) as unknown as typeof window.matchMedia;
  window.requestAnimationFrame = ((cb: FrameRequestCallback) => setTimeout(() => cb(0), 0)) as typeof window.requestAnimationFrame;
  Element.prototype.scrollIntoView = function () {};
  window.scrollTo = (() => {}) as typeof window.scrollTo;
  window.print = () => {};
  let n = 0;
  vi.spyOn(globalThis.crypto, 'randomUUID').mockImplementation(
    () => `00000000-0000-4000-8000-${String(++n).padStart(12, '0')}` as `${string}-${string}-${string}-${string}-${string}`,
  );
  let graine = 42;
  vi.spyOn(Math, 'random').mockImplementation(() => {
    graine = (graine * 1103515245 + 12345) % 2147483648;
    return graine / 2147483648;
  });
  return rec;
}

const pause = (ms = 0) => new Promise((r) => setTimeout(r, ms));

function el(sel: string): HTMLElement {
  const e = document.querySelector<HTMLElement>(sel);
  if (!e) throw new Error(`élément introuvable : ${sel}`);
  return e;
}

async function jouer(actions: Action[], rec: Enregistrement) {
  for (const a of actions) {
    if ('clic' in a) el(a.clic).click();
    else if ('saisir' in a) {
      const i = el(a.saisir) as HTMLInputElement;
      i.focus();
      i.value = a.valeur;
      i.dispatchEvent(new Event('input', { bubbles: true }));
      i.dispatchEvent(new Event('change', { bubbles: true }));
      i.dispatchEvent(new Event('blur'));
    } else if ('choisir' in a) {
      const s = el(a.choisir) as HTMLSelectElement;
      s.value = a.valeur;
      s.dispatchEvent(new Event('change', { bubbles: true }));
    } else if ('cocher' in a) {
      const c = el(a.cocher) as HTMLInputElement;
      if (!c.checked) c.click();
    } else if ('attendre' in a) await pause(10);
    else if ('envoyer' in a) {
      (el('#mt-form') as HTMLFormElement).dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
      for (let k = 0; k < 50 && rec.lead.length === 0; k++) await pause(5);
    }
    await pause();
  }
}

/** Exécute un parcours dans une locale ; rend le corps du lead (jetons masqués). */
async function executer(locale: Locale, parcours: string): Promise<Record<string, unknown>> {
  delete (ecrans[parcours] ||= {})[locale];
  const html = builtPage(ROUTES[locale]);
  const chunk = chunkDeLaPage(html);
  sessionStorage.clear();
  localStorage.clear();
  const avant = AVANT_CHARGEMENT[parcours] ?? {};
  for (const [k, v] of Object.entries(avant.local ?? {})) localStorage.setItem(k, v);
  for (const [k, v] of Object.entries(avant.session ?? {})) sessionStorage.setItem(k, v);
  monterDom(html, ROUTES[locale]);
  const rec = bouchonner();
  vi.resetModules();
  await import(/* @vite-ignore */ chunk);
  await pause(10);
  await jouer(PARCOURS[parcours], rec);
  const erreur = document.getElementById('mt-error');
  expect(rec.lead, `aucun POST /api/capture-lead (${locale}/${parcours}) — erreur affichée : « ${erreur && !erreur.hidden ? erreur.textContent : ''} »`).toHaveLength(1);
  await pause(30); // laisse les balises (FileReader) arriver
  (ecrans[parcours] ||= {})[locale] = instantaneEcran(rec);
  const corps = { ...rec.lead[0] };
  for (const [cle, forme] of Object.entries(JETONS)) {
    if (cle in corps) {
      expect(String(corps[cle]), `${cle} (${locale}/${parcours})`).toMatch(forme);
      corps[cle] = `<${cle}>`;
    }
  }
  return corps;
}

// ── RWEB17-M9 : filet d'ÉCRAN — instantané TEXTE de l'écran au moment de l'envoi ──
const normaliser = (s: string | null | undefined) => (s ?? '').replace(/\s+/g, ' ').trim();

/** Texte normalisé + `hidden` des zones d'estimation / d'erreur / de succès, libellés d'étape,
 *  `hidden` des éléments `mt-*`, `aria-pressed` des cartes, et la suite des balises de funnel. */
function instantaneEcran(rec: Enregistrement): Record<string, unknown> {
  const zones: Record<string, unknown> = {};
  const zoneIds = ['mt-estimate-announce', 'mt-error', 'mt-success', ...Array.from(document.querySelectorAll('[id^="mt-est-"]')).map((e) => e.id)];
  for (const id of [...new Set(zoneIds)].sort()) {
    const e = document.getElementById(id);
    zones[id] = e ? { texte: normaliser(e.textContent), hidden: e.hidden } : null;
  }
  const cartes: Record<string, string> = {};
  document.querySelectorAll<HTMLElement>('[aria-pressed]').forEach((e, i) => {
    const donnees = Object.entries(e.dataset).map(([k, v]) => `${k}=${v}`).join(',');
    cartes[`${String(i).padStart(3, '0')} ${e.id || e.className} ${donnees}`.trim()] = e.getAttribute('aria-pressed') ?? '';
  });
  return {
    libellesEtapes: Array.from(document.querySelectorAll('.mt-step-label')).map((e) => normaliser(e.textContent)),
    masques: Array.from(document.querySelectorAll<HTMLElement>('[id^="mt-"]')).filter((e) => e.hidden).map((e) => e.id).sort(),
    zones,
    cartes,
    balises: rec.balises,
  };
}
const ecrans: Record<string, Partial<Record<Locale, Record<string, unknown>>>> = {};

// ── les tests ────────────────────────────────────────────────────────────────
const corps: Record<string, Partial<Record<Locale, Record<string, unknown>>>> = {};

beforeAll(() => {
  vi.useFakeTimers({ toFake: ['Date'], now: new Date('2026-10-28T10:00:00+01:00') });
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe('RWEB17 (filet) — le tunnel mon-toit EXÉCUTÉ, corps du lead par locale × parcours', () => {
  for (const parcours of Object.keys(PARCOURS)) {
    for (const locale of LOCALES) {
      it(`${parcours} · ${locale} — corps identique au golden`, async () => {
        const c = await executer(locale, parcours);
        (corps[parcours] ||= {})[locale] = c;
        const trie = Object.fromEntries(Object.keys(c).sort().map((k) => [k, c[k]]));
        await expect(`${JSON.stringify(trie, null, 2)}\n`).toMatchFileSnapshot(
          `./__snapshots__/tunnelExecution/${parcours}.${locale}.json`,
        );
      }, 60_000); // 1er import à froid du chunk (transformation vite) : plusieurs secondes.
      it(`tunnelEcran · ${parcours} · ${locale} — écran identique au golden`, async () => {
        const e = ecrans[parcours]?.[locale];
        expect(e, `écran ${parcours}/${locale} non enregistré (le test du corps précédent a échoué ?)`).toBeDefined();
        await expect(`${JSON.stringify(e, null, 2)}\n`).toMatchFileSnapshot(
          `./__snapshots__/tunnelEcran/${parcours}.${locale}.json`,
        );
      });
    }
    it(`${parcours} — FR, EN et AR envoient le MÊME corps (hors clés propres à la locale)`, () => {
      const parLocale = corps[parcours];
      for (const l of LOCALES) expect(parLocale?.[l], `corps ${l} non enregistré`).toBeDefined();
      for (const [cle, attendu] of Object.entries(CLES_PROPRES_A_LA_LOCALE)) {
        for (const l of LOCALES) expect(parLocale![l]![cle], `${cle} en ${l}`).toEqual(attendu[l]);
      }
      for (const [sousCle, forme] of Object.entries(SOUS_CLES_ESTIMATION_PROPRES_A_LA_LOCALE)) {
        for (const l of LOCALES) {
          const v = (parLocale![l]!.estimateShown as Record<string, unknown> | undefined)?.[sousCle];
          if (v !== undefined) expect(v, `estimateShown.${sousCle} en ${l}`).toMatch(forme[l]);
        }
      }
      const sans = (c: Record<string, unknown>) => {
        const r = Object.fromEntries(Object.entries(c).filter(([k]) => !(k in CLES_PROPRES_A_LA_LOCALE)));
        if (r.estimateShown && typeof r.estimateShown === 'object') {
          r.estimateShown = Object.fromEntries(Object.entries(r.estimateShown as Record<string, unknown>)
            .filter(([k]) => !(k in SOUS_CLES_ESTIMATION_PROPRES_A_LA_LOCALE)));
        }
        return r;
      };
      expect(sans(parLocale!.en!), 'EN ≠ FR').toEqual(sans(parLocale!.fr!));
      expect(sans(parLocale!.ar!), 'AR ≠ FR').toEqual(sans(parLocale!.fr!));
    });
  }
});

// RWEB17-M12 — étape 0 → étape 1 puis RETOUR ARRIÈRE (popstate), joués dans les 5 parcours × 3 locales
// sur le chunk construit : le panneau affiché et `history.state` suivent, sans erreur.
describe('RWEB17-M12 — étapes et retour arrière (popstate) du tunnel EXÉCUTÉ', () => {
  for (const parcours of Object.keys(PARCOURS)) {
    for (const locale of LOCALES) {
      it(`${parcours} · ${locale} — 0 → 1, popstate → 0, puis 1 à nouveau`, async () => {
        const html = builtPage(ROUTES[locale]);
        const chunk = chunkDeLaPage(html);
        sessionStorage.clear();
        localStorage.clear();
        monterDom(html, ROUTES[locale]);
        bouchonner();
        vi.resetModules();
        await import(/* @vite-ignore */ chunk);
        await pause(10);
        const panneau = (i: number) => !(el(`#mt-panel-${i}`) as HTMLElement).hidden;
        expect(panneau(0) && !panneau(1)).toBe(true);
        const premier = PARCOURS[parcours][0] as { clic: string };
        el(premier.clic).click();
        el('#mt-next-0').click();
        await pause();
        expect(panneau(1) && !panneau(0)).toBe(true);
        expect((history.state as { mtStep?: number } | null)?.mtStep).toBe(1);
        window.dispatchEvent(new PopStateEvent('popstate', { state: { mtStep: 0, mtRevealed: false } }));
        await pause();
        expect(panneau(0) && !panneau(1)).toBe(true);
        el('#mt-next-0').click();
        await pause();
        expect(panneau(1) && !panneau(0)).toBe(true);
      }, 60_000);
    }
  }
});

/** RWEB17-M18 — le chunk de la page et ses imports STATIQUES relatifs (récursivement) : la logique
 *  du tunnel vit désormais dans un chunk partagé par les trois pages (lib/tunnel/*), que le chunk
 *  de page importe — c'est ce que le navigateur (et le harness, par `import()`) exécute. */
function sourceExecutee(chunk: string): string {
  const vus = new Set<string>();
  const lire = (chemin: string): string => {
    if (vus.has(chemin) || !existsSync(chemin)) return '';
    vus.add(chemin);
    const src = readFileSync(chemin, 'utf-8');
    const imports = [...src.matchAll(/(?:^|[;}\s])(?:import\s*|from\s*)"(\.\/[^"]+\.js)"/g)].map((m) => m[1]);
    return src + imports.map((rel) => lire(join(dirname(chemin), rel))).join('\n');
  };
  return lire(chunk);
}

it('le harness lit bien le chunk RÉELLEMENT référencé par chaque page', () => {
  for (const l of LOCALES) {
    const src = sourceExecutee(chunkDeLaPage(builtPage(ROUTES[l])));
    expect(src).toContain('/api/capture-lead');
  }
});
