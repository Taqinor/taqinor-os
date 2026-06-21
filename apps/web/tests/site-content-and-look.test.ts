// SUITE « CONTENU & LOOK DU SITE » — pilotée par données sur la SORTIE CONSTRUITE.
//
// Contrairement aux gardes existantes (seo-pages.test.ts) qui lisent le SOURCE
// .astro, cette suite parcourt le HTML RÉELLEMENT RENDU dans dist/client/ et
// affirme, page publique par page publique (liste dérivée du sitemap, jamais
// devinée), le contrat SEO/NAP/JSON-LD/liens/images, plus les gardes de
// contenu (tarif sélectif, zéro faux témoignage) et de « look » atteignables
// sans navigateur (polices auto-hébergées, mouvement réduit, count-up sans CLS).
//
// La fidélité visuelle réelle reste Lighthouse + le téléphone du fondateur.
//
// Le job CI `web-build-test` lance `astro build` AVANT `vitest`, donc dist est
// toujours frais sur le runner. En local, ensureBuilt() reconstruit dist
// seulement s'il manque ou s'il est périmé (une source plus récente que le
// build) — aucune clé/secret requis : tout est lu sur disque, la frontière
// webhook/CAPI est injectée (mock) dans le test de flux lead.
import { describe, expect, it } from 'vitest';
import { execSync } from 'node:child_process';
import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { NAP, WHATSAPP_LEADS } from '../src/lib/nap';
import { BILL_RANGES } from '../src/lib/billRange';
import { ROOF_TYPES, validateLead, runSimulation, buildLeadRecord, forwardLead, fireCapi, type LeadEnv } from '../src/lib/lead';
import { whatsappLink, leadWhatsappText } from '../src/lib/whatsapp';
import { REALISATIONS, CITIES } from '../src/lib/realisations';
import { ui } from '../src/i18n/ui';

const uiFr = ui.fr as Record<string, string>;

// ───────────────────────── chemins & build ─────────────────────────
const webRoot = fileURLToPath(new URL('..', import.meta.url));
const distClient = fileURLToPath(new URL('../dist/client/', import.meta.url));
const read = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');

function newestMtimeMs(dir: string): number {
  let newest = 0;
  const stack = [dir];
  while (stack.length) {
    const d = stack.pop()!;
    for (const name of readdirSync(d)) {
      const full = `${d}/${name}`;
      const st = statSync(full);
      if (st.isDirectory()) stack.push(full);
      else if (st.mtimeMs > newest) newest = st.mtimeMs;
    }
  }
  return newest;
}

/**
 * Garantit un dist/client à jour. Reconstruit UNIQUEMENT si dist manque ou si
 * une source (src, public, configs) est plus récente que le build — en CI le
 * build vient de tourner, donc rien ne se reconstruit ici.
 */
function ensureBuilt(): void {
  const indexHtml = `${distClient}index.html`;
  let stale = !existsSync(indexHtml);
  if (!stale) {
    const distMs = statSync(indexHtml).mtimeMs;
    const srcMs = Math.max(
      newestMtimeMs(`${webRoot}src`),
      existsSync(`${webRoot}public`) ? newestMtimeMs(`${webRoot}public`) : 0,
      statSync(`${webRoot}astro.config.mjs`).mtimeMs,
      statSync(`${webRoot}package.json`).mtimeMs,
    );
    stale = srcMs > distMs;
  }
  if (!stale) return;
  try {
    execSync('npm run build', { cwd: webRoot, stdio: 'pipe', timeout: 240000 });
  } catch (e) {
    const out = e && typeof e === 'object' && 'stdout' in e ? String((e as { stdout?: Buffer }).stdout ?? '') : '';
    const err = e && typeof e === 'object' && 'stderr' in e ? String((e as { stderr?: Buffer }).stderr ?? '') : '';
    throw new Error(`[site-content-and-look] « astro build » a échoué — la page ne rend pas sans erreur.\n${out}\n${err}`);
  }
  if (!existsSync(indexHtml)) throw new Error('[site-content-and-look] dist/client introuvable après le build.');
}

// Construit le site (ou réutilise le build CI), AVANT la collecte des cas data-driven.
ensureBuilt();

// ───────────────────── inventaire des routes ─────────────────────
const sitemapXml = readFileSync(`${distClient}sitemap-0.xml`, 'utf-8');
const sitemapLocs = [...sitemapXml.matchAll(/<loc>([^<]+)<\/loc>/g)].map((m) => m[1]);

interface Route {
  loc: string; // URL encodée du sitemap (forme canonique attendue)
  path: string; // chemin décodé, ex. /à-propos/
  file: string; // fichier dist correspondant
}

function locToRoute(loc: string): Route {
  const path = decodeURIComponent(new URL(loc).pathname);
  const segs = path.split('/').filter(Boolean);
  const file = segs.length ? `${distClient}${segs.join('/')}/index.html` : `${distClient}index.html`;
  return { loc, path, file };
}

const publicRoutes: Route[] = sitemapLocs.map(locToRoute);

// Toutes les routes RÉELLEMENT construites (pour dériver les routes privées).
function builtRoutePaths(): string[] {
  const out: string[] = [];
  const walk = (dir: string, prefix: string) => {
    for (const name of readdirSync(dir)) {
      const full = `${dir}/${name}`;
      if (statSync(full).isDirectory()) walk(full, `${prefix}${name}/`);
      else if (name === 'index.html') out.push(prefix === '' ? '/' : `/${prefix}`);
    }
  };
  walk(distClient.replace(/\/$/, ''), '');
  return out;
}
const allBuiltPaths = builtRoutePaths();
const publicPathSet = new Set(publicRoutes.map((r) => r.path));
// Routes construites mais ABSENTES du sitemap = privées (preview).
const privatePaths = allBuiltPaths.filter((p) => !publicPathSet.has(p));

// ───────────────────── helpers de parsing HTML ─────────────────────
const html = (file: string) => readFileSync(file, 'utf-8');

const titles = (h: string) => [...h.matchAll(/<title>([\s\S]*?)<\/title>/g)].map((m) => m[1].trim());
const metaContent = (h: string, name: string): string | null => {
  const re = new RegExp(`<meta[^>]*name="${name}"[^>]*content="([^"]*)"|<meta[^>]*content="([^"]*)"[^>]*name="${name}"`, 'i');
  const m = h.match(re);
  return m ? (m[1] ?? m[2] ?? '') : null;
};
const ogContent = (h: string, prop: string): string | null => {
  const re = new RegExp(`<meta[^>]*property="${prop}"[^>]*content="([^"]*)"`, 'i');
  const m = h.match(re);
  return m ? m[1] : null;
};
const canonicalHref = (h: string): string | null => {
  const m = h.match(/<link[^>]*rel="canonical"[^>]*href="([^"]*)"/i);
  return m ? m[1] : null;
};
function jsonLdBlocks(h: string): unknown[] {
  const out: unknown[] = [];
  for (const m of h.matchAll(/<script type="application\/ld\+json"[^>]*>([\s\S]*?)<\/script>/g)) {
    out.push(JSON.parse(m[1]));
  }
  return out;
}
const jsonLdRootTypes = (h: string) =>
  jsonLdBlocks(h).map((d) => (d && typeof d === 'object' ? (d as { '@type'?: string })['@type'] : undefined));
const imgTags = (h: string) => [...h.matchAll(/<img\b[^>]*>/g)].map((m) => m[0]);
const imgHasAlt = (tag: string) => /\salt(\s*=|\s|\/|>)/.test(tag);
const imgAltEmpty = (tag: string) => {
  const m = tag.match(/\salt="([^"]*)"/);
  return m ? m[1].trim() === '' : true; // alt nu (sans =) = vide
};
const internalLinks = (h: string) =>
  [...h.matchAll(/href="([^"]+)"/g)].map((m) => m[1]).filter((href) => href.startsWith('/') && !href.startsWith('//'));

// Une route/asset interne existe-t-elle dans le build ?
const ASSET_EXT = /\.(css|js|mjs|svg|png|jpe?g|webp|avif|woff2?|xml|ico|txt|json|webmanifest|mp4|webm|pdf)$/i;
function internalTargetExists(href: string): boolean {
  const clean = decodeURIComponent(href.split('#')[0].split('?')[0]);
  if (clean === '' || clean === '/') return existsSync(`${distClient}index.html`);
  const rel = clean.replace(/^\/+/, '').replace(/\/+$/, '');
  if (ASSET_EXT.test(clean)) return existsSync(`${distClient}${rel}`);
  // Une route : forme /x ou /x/ → dist/client/x/index.html (ou x.html).
  return existsSync(`${distClient}${rel}/index.html`) || existsSync(`${distClient}${rel}.html`);
}

const publicHtml = publicRoutes.map((r) => ({ r, h: html(r.file) }));

// ───────────────────────── tests ─────────────────────────
describe('inventaire des routes (sortie construite réelle)', () => {
  it('le sitemap liste les pages publiques attendues (site élargi)', () => {
    expect(publicRoutes.length).toBeGreaterThanOrEqual(30);
    for (const must of ['/', '/faq/', '/guides/', '/à-propos/', '/garanties/', '/pourquoi-taqinor/',
      '/marocains-du-monde/', '/realisations/', '/installation-solaire-casablanca/', '/contact/']) {
      expect(publicPathSet.has(must), `sitemap manque ${must}`).toBe(true);
    }
  });

  it('les routes privées construites sont toutes des /preview/* (hors sitemap)', () => {
    expect(privatePaths.length).toBeGreaterThan(0);
    for (const p of privatePaths) expect(p.startsWith('/preview/'), `privée inattendue : ${p}`).toBe(true);
    // L'estimateur courant (pro-11) est bien une route privée.
    expect(privatePaths).toContain('/preview/toiture-3d-pro-11/');
  });
});

describe('chaque page publique — contrat SEO rendu', () => {
  // Locale attendue d'après le préfixe de l'URL (FR à la racine, EN sous /en/,
  // AR sous /ar/ avec dir=rtl). W67 : le site est multilingue, l'attribut lang
  // n'est donc plus universellement « fr ».
  const expectedLang = (path: string): 'fr' | 'en' | 'ar' =>
    path.startsWith('/en/') ? 'en' : path.startsWith('/ar/') ? 'ar' : 'fr';

  it.each(publicHtml.map(({ r }) => r.path))('%s rend sans erreur (HTML non vide)', (p) => {
    const { h } = publicHtml.find((x) => x.r.path === p)!;
    expect(h.length).toBeGreaterThan(500);
    expect(h).toContain(`<html lang="${expectedLang(p)}"`);
    if (expectedLang(p) === 'ar') expect(h).toContain('dir="rtl"');
    expect(h).toContain('</html>');
  });

  it.each(publicHtml.map(({ r }) => r.path))('%s : exactement un <title> non vide', (p) => {
    const { h } = publicHtml.find((x) => x.r.path === p)!;
    const t = titles(h);
    expect(t).toHaveLength(1);
    expect(t[0].length).toBeGreaterThan(0);
  });

  it.each(publicHtml.map(({ r }) => r.path))('%s : meta description non vide', (p) => {
    const { h } = publicHtml.find((x) => x.r.path === p)!;
    const d = metaContent(h, 'description');
    expect(d, 'meta description absente').not.toBeNull();
    expect((d ?? '').length).toBeGreaterThan(10);
  });

  it.each(publicHtml.map(({ r }) => r.path))('%s : canonical auto-référent (forme à slash final du sitemap)', (p) => {
    const { r, h } = publicHtml.find((x) => x.r.path === p)!;
    expect(canonicalHref(h)).toBe(r.loc);
    expect(r.loc.endsWith('/')).toBe(true);
  });

  it.each(publicHtml.map(({ r }) => r.path))('%s : INDEXABLE (aucun noindex)', (p) => {
    const { h } = publicHtml.find((x) => x.r.path === p)!;
    const robots = metaContent(h, 'robots');
    if (robots !== null) expect(robots.toLowerCase()).not.toContain('noindex');
  });

  it.each(publicHtml.map(({ r }) => r.path))('%s : og:image présente', (p) => {
    const { h } = publicHtml.find((x) => x.r.path === p)!;
    const og = ogContent(h, 'og:image');
    expect(og, 'og:image absente').not.toBeNull();
    expect((og ?? '').length).toBeGreaterThan(0);
  });

  it.each(publicHtml.map(({ r }) => r.path))('%s : LocalBusiness JSON-LD valide, NAP aligné', (p) => {
    const { h } = publicHtml.find((x) => x.r.path === p)!;
    const blocks = jsonLdBlocks(h) as Array<Record<string, unknown>>;
    const lb = blocks.find((b) => b['@type'] === 'LocalBusiness');
    expect(lb, 'LocalBusiness JSON-LD absent').toBeTruthy();
    expect(lb!.name).toBe(NAP.name);
    expect(lb!.url).toBe(NAP.url);
    expect(lb!.telephone).toBe(NAP.phone);
    expect(lb!.email).toBe(NAP.email);
    expect(Array.isArray(lb!.areaServed)).toBe(true);
  });

  it.each(publicHtml.map(({ r }) => r.path))('%s : chaque <img> porte un attribut alt', (p) => {
    const { h } = publicHtml.find((x) => x.r.path === p)!;
    for (const tag of imgTags(h)) {
      expect(imgHasAlt(tag), `img sans alt : ${tag.slice(0, 80)}`).toBe(true);
    }
  });

  it.each(publicHtml.map(({ r }) => r.path))('%s : tout lien interne pointe vers une route/asset existante', (p) => {
    const { h } = publicHtml.find((x) => x.r.path === p)!;
    const dead = [...new Set(internalLinks(h))].filter((href) => !internalTargetExists(href));
    expect(dead, `liens internes morts sur ${p} : ${dead.join(', ')}`).toEqual([]);
  });
});

describe('données structurées par famille de page', () => {
  it('LocalBusiness présent sur TOUTES les pages publiques', () => {
    for (const { r, h } of publicHtml) {
      expect(jsonLdRootTypes(h), `${r.path} sans LocalBusiness`).toContain('LocalBusiness');
    }
  });

  it('FAQPage présent sur /faq et ABSENT de l’accueil (pas de doublon W19)', () => {
    const faq = publicHtml.find((x) => x.r.path === '/faq/')!;
    const home = publicHtml.find((x) => x.r.path === '/')!;
    expect(jsonLdRootTypes(faq.h)).toContain('FAQPage');
    expect(home.h).not.toContain('"@type":"FAQPage"');
  });

  it('Article JSON-LD sur chaque étude de cas et chaque guide rédactionnel', () => {
    const caseStudies = publicHtml.filter((x) => /^\/realisations\/.+\//.test(x.r.path));
    const guides = publicHtml.filter((x) => /^\/guides\/.+\//.test(x.r.path));
    expect(caseStudies.length).toBeGreaterThanOrEqual(5);
    expect(guides.length).toBeGreaterThanOrEqual(3);
    for (const x of [...caseStudies, ...guides]) {
      expect(jsonLdRootTypes(x.h), `${x.r.path} sans Article`).toContain('Article');
    }
  });

  it('Service avec areaServed (City) sur chaque page ville', () => {
    const cityPages = publicHtml.filter((x) => /^\/installation-solaire-/.test(x.r.path));
    expect(cityPages.length).toBeGreaterThanOrEqual(5);
    for (const x of cityPages) {
      const svc = (jsonLdBlocks(x.h) as Array<Record<string, unknown>>).find((b) => b['@type'] === 'Service');
      expect(svc, `${x.r.path} sans Service`).toBeTruthy();
      expect(svc!.areaServed, `${x.r.path} Service sans areaServed`).toBeTruthy();
    }
  });
});

describe('NAP — une seule vérité, zéro divergence', () => {
  // Formes téléphoniques autorisées (réduites aux chiffres pour comparaison).
  const allowedDigits = new Set([
    NAP.phone.replace(/\D/g, ''), // 212661850410
    NAP.phoneDisplay.replace(/\D/g, ''), // 0661850410
    NAP.phoneDisplayIntl.replace(/\D/g, ''), // 212661850410
    WHATSAPP_LEADS.replace(/\D/g, ''), // 212661850410
  ]);

  it('tout lien tel: pointe vers le E.164 NAP', () => {
    for (const { r, h } of publicHtml) {
      for (const m of h.matchAll(/href="tel:([^"]+)"/g)) {
        expect(m[1], `tel: divergent sur ${r.path}`).toBe(NAP.phone);
      }
    }
  });

  it('tout lien wa.me utilise le numéro WhatsApp leads', () => {
    for (const { r, h } of publicHtml) {
      for (const m of h.matchAll(/wa\.me\/(\d+)/g)) {
        expect(m[1], `wa.me divergent sur ${r.path}`).toBe(WHATSAPP_LEADS.replace(/\D/g, ''));
      }
    }
  });

  it('aucun numéro marocain affiché ne diverge des formes NAP', () => {
    const phoneRe = /\+212[\s ]?[5-7][\d\s .]{8,15}|\b0[5-7](?:[\s .]?\d{2}){4}\b/g;
    for (const { r, h } of publicHtml) {
      // On scanne le texte visible (balises retirées) pour éviter les ids/classes.
      const text = h.replace(/<script[\s\S]*?<\/script>/g, ' ').replace(/<style[\s\S]*?<\/style>/g, ' ').replace(/<[^>]+>/g, ' ');
      for (const m of text.matchAll(phoneRe)) {
        const digits = m[0].replace(/\D/g, '');
        expect(allowedDigits.has(digits), `numéro divergent « ${m[0].trim()} » sur ${r.path}`).toBe(true);
      }
    }
  });

  it('tout mailto: pointe vers l’email NAP', () => {
    for (const { r, h } of publicHtml) {
      for (const m of h.matchAll(/href="mailto:([^"?]+)/g)) {
        expect(m[1], `mailto divergent sur ${r.path}`).toBe(NAP.email);
      }
    }
  });
});

describe('navigation & maillage', () => {
  const header = read('../src/components/Header.astro');
  const footer = read('../src/components/Footer.astro');

  it('l’en-tête contient les vrais items courants', () => {
    for (const href of ['/guides', '/faq', '/à-propos']) expect(header).toContain(href);
  });

  it('le pied de page lie le légal, les guides et les réalisations', () => {
    for (const href of ['/mentions-legales', '/politique-de-confidentialite', '/guides', '/realisations', '/garanties']) {
      expect(footer, href).toContain(href);
    }
  });
});

describe('routes privées /preview/* — jamais indexées, jamais liées', () => {
  it.each(privatePaths)('%s : noindex + hors sitemap', (p) => {
    const segs = p.split('/').filter(Boolean);
    const h = html(`${distClient}${segs.join('/')}/index.html`);
    const robots = metaContent(h, 'robots');
    expect(robots, `${p} sans meta robots`).not.toBeNull();
    expect((robots ?? '').toLowerCase()).toContain('noindex');
    expect(publicPathSet.has(p)).toBe(false);
  });

  it('aucune page publique ne lie une route /preview/*', () => {
    for (const { r, h } of publicHtml) {
      const leaks = internalLinks(h).filter((href) => href.includes('/preview/'));
      expect(leaks, `${r.path} lie une preview : ${leaks.join(', ')}`).toEqual([]);
    }
  });
});

describe('contenu — exactitude (régressions passées)', () => {
  it('aucun faux témoignage ni placeholder « témoignage à venir »', () => {
    for (const { r, h } of publicHtml) {
      expect(h.toLowerCase(), `${r.path} contient « témoignage »`).not.toContain('témoignage');
    }
  });

  it('la carte de confiance est recadrée (pas de décompte de projets trompeur)', () => {
    const { h } = publicHtml.find((x) => x.r.path === '/')!;
    expect(h).toContain('Chantiers visitables');
    expect(h).not.toContain('>5 projets<');
    expect(h).not.toContain('livrés depuis 2025');
  });

  it('le tarif électrique = barème sélectif, jamais l’ancien plat 1,4 MAD/kWh', () => {
    const flat = /1[.,]4\s*(MAD|DH|dh)\s*\/?\s*kWh/i;
    for (const { r, h } of publicHtml) {
      const text = h.replace(/<[^>]+>/g, ' ');
      expect(flat.test(text), `${r.path} cite 1,4 MAD/kWh comme base tarifaire`).toBe(false);
    }
  });
});

describe('look (atteignable sans navigateur)', () => {
  const globalCss = read('../src/styles/global.css');
  const v2enhance = read('../src/components/V2Enhance.astro');

  it('Archivo + Hanken Grotesk sont AUTO-HÉBERGÉS (pas de CDN Google)', () => {
    expect(globalCss).toContain("font-family: 'Archivo'");
    expect(globalCss).toContain("font-family: 'Hanken Grotesk'");
    expect(globalCss).toMatch(/url\('\/fonts\/archivo-[^']+\.woff2'\)/);
    expect(globalCss).toMatch(/url\('\/fonts\/hanken-[^']+\.woff2'\)/);
    expect(globalCss).not.toContain('fonts.googleapis.com');
    expect(globalCss).not.toContain('fonts.gstatic.com');
  });

  it('aucune page construite ne charge une police via un CDN Google', () => {
    for (const { r, h } of publicHtml) {
      expect(h, `${r.path} charge un CDN Google`).not.toContain('fonts.googleapis.com');
      expect(h).not.toContain('fonts.gstatic.com');
    }
  });

  it('les jetons de design (variables CSS) sont présents', () => {
    expect(globalCss).toMatch(/--color-[\w-]+:/);
    expect(globalCss).toMatch(/--font-(display|sans)/);
  });

  it('un chemin prefers-reduced-motion coupe le mouvement', () => {
    expect(v2enhance).toContain("matchMedia('(prefers-reduced-motion: reduce)')");
    expect(v2enhance).toMatch(/if\s*\(\s*!reduce/); // tout le mouvement est gardé derrière !reduce
  });

  it('le count-up verrouille sa largeur (anti-CLS) et fixe la valeur finale exacte', () => {
    expect(v2enhance).toContain('minWidth');
    expect(v2enhance).toContain('el.textContent = finalText'); // valeur finale exacte
  });
});

// ───────── LE FORMULAIRE (diagnostic 3 étapes) — structure & câblage ─────────
describe('le formulaire — structure 3 étapes & champs requis', () => {
  const form = read('../src/components/DiagnosticForm.astro');

  it('expose 3 étapes (fieldsets data-step) avec indicateur « Étape 1 sur 3 »', () => {
    for (const n of [1, 2, 3]) expect(form).toContain(`data-step="${n}"`);
    // W67 — l'indicateur de progression est désormais traduit (dictionnaire) ;
    // le FR reste « Étape 1 sur 3 » à la racine. On vérifie le gabarit FR du
    // dictionnaire (source de vérité) et son rendu attendu.
    expect(uiFr['form.progress']).toBe('Étape {step} sur 3');
    expect(uiFr['form.progress'].replace('{step}', '1')).toBe('Étape 1 sur 3');
  });

  it('exige nom, téléphone (+212/E.164), ville, type de toit, tranche de facture et consentement', () => {
    expect(form).toMatch(/name="fullName"[^>]*required/);
    expect(form).toMatch(/name="phone"[^>]*required/);
    expect(form).toContain('type="tel"');
    expect(form).toMatch(/name="city"[^>]*required/);
    expect(form).toMatch(/name="roofType"[^>]*required/);
    expect(form).toMatch(/name="billRange"[^>]*required/);
    expect(form).toMatch(/name="consent"[^>]*required/);
  });

  it('case WhatsApp opt-in présente (cochée par défaut)', () => {
    expect(form).toMatch(/name="whatsappOptIn"[^>]*checked/);
  });

  it('le menu déroulant tranche de facture finit aux paliers 800/1 000/1 500/3 000/5 000/10 000+', () => {
    // Les options sont rendues depuis BILL_RANGES → on vérifie la source de vérité.
    const labels = BILL_RANGES.map((b) => b.label);
    expect(BILL_RANGES).toHaveLength(7);
    expect(labels.some((l) => /800/.test(l) && /1\s*000/.test(l))).toBe(true);
    expect(labels.some((l) => /1\s*000/.test(l) && /1\s*500/.test(l))).toBe(true);
    expect(labels.some((l) => /5\s*000/.test(l) && /10\s*000/.test(l))).toBe(true);
    expect(labels.some((l) => /10\s*000/.test(l))).toBe(true);
    expect(form).toContain('BILL_RANGES.map');
    // Les 4 types de toit du brief sont rendus depuis ROOF_TYPES.
    expect(ROOF_TYPES.length).toBeGreaterThanOrEqual(4);
    expect(form).toContain('ROOF_TYPES.map');
  });

  it('capture fbclid + les 5 UTM en champs cachés', () => {
    for (const k of ['fbclid', 'utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term']) {
      expect(form).toContain(`name="${k}"`);
    }
  });

  it('ne POST QUE vers l’API interne /api/simulate — jamais un service externe depuis le navigateur', () => {
    const fetches = [...form.matchAll(/fetch\(\s*['"]([^'"]+)['"]/g)].map((m) => m[1]);
    expect(fetches.length).toBeGreaterThan(0);
    for (const url of fetches) expect(url.startsWith('/api/')).toBe(true);
    // Aucune frontière externe (webhook/CAPI/wa.me/simulateur) appelée côté client.
    for (const host of ['wa.me', 'http://', 'https://', 'webhook', 'capi', 'facebook.com']) {
      expect(form.includes(`fetch('${host}`)).toBe(false);
    }
  });

  it('soumission verrouillée à l’étape finale : abandon en cours = rien n’est envoyé', () => {
    // Le fetch vit DANS le gestionnaire submit ; les étapes 1/2 n'utilisent que
    // la validation cliente (nextStep/validateStep), sans réseau.
    expect(form).toContain("form?.addEventListener('submit'");
    const submitIdx = form.indexOf("addEventListener('submit'");
    expect(form.indexOf('fetch(', submitIdx)).toBeGreaterThan(submitIdx);
    expect(form).toContain('validateStep');
    expect(form).toContain('nextStep');
  });
});

// ───────── LE FLUX LEAD bout-en-bout — frontière webhook/CAPI MOCKÉE ─────────
describe('le flux lead — bout-en-bout (sans secret, frontière mockée)', () => {
  const base = {
    fullName: 'Yassine El Amrani',
    phone: '06 61 85 04 10',
    whatsappOptIn: true,
    city: 'Casablanca',
    roofType: 'villa',
    consent: true,
    fbclid: 'fb.1.999.xyz',
    utm_source: 'facebook',
    utm_medium: 'cpc',
    utm_campaign: 'ete',
    utm_content: 'pub-a',
    utm_term: 'solaire',
  };
  const env: LeadEnv = {
    LEAD_WEBHOOK_URL: 'https://crm.example/hook',
    LEAD_WEBHOOK_SECRET: 'test-secret',
    CAPI_URL: 'https://capi.example/events',
  };

  it('lead QUALIFIÉ (≥1 000 MAD) : ROI serveur, webhook complet + secret, CAPI Lead, deeplink +212', async () => {
    const calls: { url: string; init: RequestInit }[] = [];
    const fetchMock = (async (url: unknown, init?: RequestInit) => {
      calls.push({ url: String(url), init: init ?? {} });
      return new Response('ok', { status: 200 });
    }) as unknown as typeof fetch;

    const v = validateLead({ ...base, billRange: '1500-3000' });
    expect(v.ok).toBe(true);
    if (!v.ok) return;
    expect(v.lead.phoneE164).toBe('+212661850410'); // normalisation E.164 +212

    const band = await runSimulation(v.lead, env, fetchMock); // ROI calculé côté serveur
    expect(band.kwcLabel.length).toBeGreaterThan(0);
    expect(band.paybackLabel.length).toBeGreaterThan(0);

    const record = buildLeadRecord(v.lead, band, new Date('2026-06-18T09:00:00Z'), '/');
    expect(record.qualified).toBe(true);
    expect(record.consentTimestamp).toBe('2026-06-18T09:00:00.000Z');

    const fw = await forwardLead(record, env, fetchMock);
    expect(fw.delivered).toBe(true);
    const hook = calls.find((c) => c.url === env.LEAD_WEBHOOK_URL)!;
    expect((hook.init.headers as Record<string, string>)['x-webhook-secret']).toBe('test-secret');
    const payload = JSON.parse(String(hook.init.body));
    expect(payload.phoneE164).toBe('+212661850410');
    expect(payload.fbclid).toBe('fb.1.999.xyz'); // fbclid persisté
    expect(payload.utm.utm_source).toBe('facebook'); // 5 UTM persistés
    expect(payload.utm.utm_term).toBe('solaire');
    expect(payload.consent).toBe(true);

    const capi = await fireCapi(record, env, fetchMock);
    expect(capi.sent).toBe(true);
    const capiCall = calls.find((c) => c.url === env.CAPI_URL)!;
    expect(JSON.parse(String(capiCall.init.body)).event).toBe('Lead');

    // Deeplink WhatsApp +212, jamais appelé depuis le navigateur (construit serveur).
    const link = whatsappLink(WHATSAPP_LEADS, leadWhatsappText({
      fullName: v.lead.fullName, city: v.lead.city, kwcLabel: band.kwcLabel, paybackLabel: band.paybackLabel,
    }));
    expect(link.startsWith('https://wa.me/212661850410?text=')).toBe(true);
  });

  it('lead SOUS le seuil (<1 000 MAD) : extrait montré, MAIS aucun webhook ni CAPI', async () => {
    const fetchMock = (async () => {
      throw new Error('aucun appel externe ne devrait partir sous le seuil');
    }) as unknown as typeof fetch;

    const v = validateLead({ ...base, billRange: '800-1000' });
    expect(v.ok).toBe(true);
    if (!v.ok) return;
    const band = await runSimulation(v.lead, {}, fetchMock); // fallback local, pas d'appel
    const record = buildLeadRecord(v.lead, band, new Date(), '/');
    expect(record.qualified).toBe(false);

    const fw = await forwardLead(record, env, fetchMock);
    expect(fw.delivered).toBe(false);
    expect(fw.reason).toBe('below-threshold');

    const capi = await fireCapi(record, env, fetchMock);
    expect(capi.sent).toBe(false);
    // band reste fournie pour l'état de remerciement.
    expect(band.kwcLabel.length).toBeGreaterThan(0);
  });
});

// Réalisations & villes : cohérence des faits structurés (intégrité éditoriale).
describe('réalisations & villes — cohérence des routes & faits', () => {
  it('chaque étude de cas réelle a une page construite dans le sitemap', () => {
    for (const rea of REALISATIONS) {
      expect(publicPathSet.has(`/realisations/${rea.slug}/`), `manque ${rea.slug}`).toBe(true);
    }
  });

  it('chaque ville de service (hors Maroc) a sa page construite', () => {
    for (const c of CITIES) {
      const slug = `/installation-solaire-${c.name.toLowerCase()}/`;
      expect(publicPathSet.has(slug), `manque ${slug}`).toBe(true);
    }
  });
});
