/**
 * Détecteurs des gardes navigateur (YBW15), partagés par les specs — et
 * réutilisables par YBW56 (crawl rejoué après un envoi de rendez-vous).
 * Chaque détecteur renvoie la LISTE des problèmes (vide = vert) pour que les
 * specs puissent prouver qu'il rougit sur une page piège avant de passer.
 */
import { existsSync, readdirSync, statSync } from 'node:fs';
import { join, relative, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import AxeBuilder from '@axe-core/playwright';
import type { Page, Request, Response } from '@playwright/test';
import { sourcesCsp } from '../src/lib/subprocessors';

export const LARGEURS = [320, 375, 768, 1440] as const;
export const CIBLE_TACTILE_MIN = 44;

const DIST_CLIENT = fileURLToPath(new URL('../dist/client/', import.meta.url));

/** URL de chaque page HTML construite (FR et EN selon les langues actives). */
export function pagesDuBuild(): string[] {
  if (!existsSync(DIST_CLIENT)) throw new Error('dist/client/ absent — lancer `npm run build` avant `npm run test:e2e`');
  const out: string[] = [];
  const parcourir = (dir: string) => {
    for (const nom of readdirSync(dir)) {
      const p = join(dir, nom);
      if (statSync(p).isDirectory()) parcourir(p);
      else if (nom === 'index.html') {
        const rel = relative(DIST_CLIENT, dir).split(sep).join('/');
        out.push(rel ? `/${rel}/` : '/');
      }
    }
  };
  parcourir(DIST_CLIENT);
  return out.sort();
}

/** Hôtes tiers autorisés = ceux du registre des sous-traitants (YBW26). */
export function hotesAutorises(): Set<string> {
  const hotes = new Set<string>();
  for (const liste of Object.values(sourcesCsp())) {
    for (const h of liste ?? []) {
      try {
        hotes.add(new URL(h).host);
      } catch {
        /* entrée non-URL (ex. 'self') : ignorée */
      }
    }
  }
  return hotes;
}

/** Débordement horizontal : `scrollWidth > clientWidth`. */
export async function debordement(page: Page): Promise<string[]> {
  const { scroll, client } = await page.evaluate(() => ({
    scroll: document.documentElement.scrollWidth,
    client: document.documentElement.clientWidth,
  }));
  return scroll > client ? [`débordement horizontal : scrollWidth ${scroll} > clientWidth ${client}`] : [];
}

/** Cibles tactiles visibles < 44 px (hors liens EN LIGNE dans un texte, exemptés par WCAG 2.5.8). */
export async function ciblesTropPetites(page: Page): Promise<string[]> {
  return page.evaluate((min) => {
    const out: string[] = [];
    const sel = 'a[href], button, input:not([type=hidden]), select, textarea, [role=button], summary';
    for (const el of Array.from(document.querySelectorAll<HTMLElement>(sel))) {
      const style = getComputedStyle(el);
      if (style.visibility === 'hidden' || style.display === 'none') continue;
      const r = el.getBoundingClientRect();
      if (r.width === 0 && r.height === 0) continue;
      if (style.display === 'inline' && el.closest('p, li, dd, figcaption, td')) continue;
      if (r.width < min || r.height < min) {
        out.push(`${el.tagName.toLowerCase()}${el.id ? '#' + el.id : ''} « ${(el.textContent || '').trim().slice(0, 30)} » ${Math.round(r.width)}×${Math.round(r.height)}`);
      }
    }
    return out;
  }, CIBLE_TACTILE_MIN);
}

/** Violations axe-core d'impact sérieux ou critique. */
export async function violationsAxe(page: Page): Promise<string[]> {
  const res = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa']).analyze();
  return res.violations
    .filter((v) => v.impact === 'serious' || v.impact === 'critical')
    .map((v) => `${v.id} (${v.impact}) : ${v.nodes.length} nœud(s) — ${v.help}`);
}

/**
 * Sondes injectées AVANT tout script de la page : écritures de stockage,
 * enregistrements de service worker, violations CSP.
 */
export async function installerSondes(page: Page): Promise<void> {
  await page.addInitScript(() => {
    const g: { stockage: string[]; sw: string[]; csp: string[] } = { stockage: [], sw: [], csp: [] };
    (window as unknown as { __gardes: typeof g }).__gardes = g;
    const setItem = Storage.prototype.setItem;
    Storage.prototype.setItem = function (this: Storage, k: string, v: string) {
      g.stockage.push(`${this === window.localStorage ? 'localStorage' : 'sessionStorage'}.${k}`);
      return setItem.call(this, k, v);
    };
    if (navigator.serviceWorker) {
      const register = navigator.serviceWorker.register.bind(navigator.serviceWorker);
      navigator.serviceWorker.register = (url: string | URL, opts?: RegistrationOptions) => {
        g.sw.push(String(url));
        return register(url, opts);
      };
    }
    document.addEventListener('securitypolicyviolation', (e) => {
      g.csp.push(`${e.violatedDirective} ← ${e.blockedURI || 'inline'}`);
    });
  });
}

/**
 * Charge `url` et renvoie TOUS les problèmes : erreurs console / pageerror,
 * requêtes échouées ou ≥ 400, `Set-Cookie`, cookie non vide, écritures de
 * stockage, service worker, violations CSP, requêtes vers un hôte absent du
 * registre. `installerSondes(page)` doit avoir été appelé avant.
 */
export async function crawler(page: Page, url: string): Promise<string[]> {
  const problemes: string[] = [];
  const autorises = hotesAutorises();
  const surConsole = (m: { type(): string; text(): string }) => {
    if (m.type() === 'error') problemes.push(`console.error : ${m.text()}`);
  };
  const surErreur = (e: Error) => problemes.push(`pageerror : ${e.message}`);
  const surEchec = (r: { url(): string; failure(): { errorText: string } | null }) =>
    problemes.push(`requête échouée : ${r.url()} (${r.failure()?.errorText})`);
  const enAttente: Promise<void>[] = [];
  const surReponse = (r: Response) => {
    if (r.status() >= 400) problemes.push(`HTTP ${r.status()} : ${r.url()}`);
    enAttente.push(
      r.allHeaders().then((h) => {
        if (h['set-cookie']) problemes.push(`Set-Cookie sur ${r.url()}`);
      }),
    );
  };
  // L'origine du site = celle de la première navigation du cadre principal.
  let origine: string | null = null;
  const surRequete = (r: Request) => {
    const u = new URL(r.url());
    if (!/^https?:$/.test(u.protocol)) return;
    if (origine === null && r.isNavigationRequest() && r.frame() === page.mainFrame()) origine = u.host;
    if (u.host !== origine && !autorises.has(u.host)) problemes.push(`hôte hors registre : ${u.host}`);
  };
  page.on('console', surConsole);
  page.on('pageerror', surErreur);
  page.on('requestfailed', surEchec);
  page.on('response', surReponse);
  page.on('request', surRequete);
  try {
    await page.goto(url, { waitUntil: 'networkidle' });
    const etat = await page.evaluate(async () => {
      const g = (window as unknown as { __gardes?: { stockage: string[]; sw: string[]; csp: string[] } }).__gardes;
      const regs = navigator.serviceWorker ? await navigator.serviceWorker.getRegistrations() : [];
      return {
        cookie: document.cookie,
        stockage: g?.stockage ?? ['sondes non installées'],
        sw: [...(g?.sw ?? []), ...regs.map((r) => r.scope)],
        csp: g?.csp ?? [],
        local: localStorage.length,
        session: sessionStorage.length,
      };
    });
    if (etat.cookie) problemes.push(`document.cookie non vide : ${etat.cookie}`);
    const cookies = await page.context().cookies();
    if (cookies.length) problemes.push(`cookie posé : ${cookies.map((c) => c.name).join(', ')}`);
    await page.context().clearCookies();
    for (const s of etat.stockage) problemes.push(`écriture de stockage : ${s}`);
    if (etat.local || etat.session) problemes.push(`stockage non vide (local ${etat.local}, session ${etat.session})`);
    for (const s of etat.sw) problemes.push(`service worker : ${s}`);
    for (const c of etat.csp) problemes.push(`violation CSP : ${c}`);
    await Promise.all(enAttente);
  } finally {
    page.off('console', surConsole);
    page.off('pageerror', surErreur);
    page.off('requestfailed', surEchec);
    page.off('response', surReponse);
    page.off('request', surRequete);
  }
  return problemes;
}
