// WAUD59 — garde transversale sur le HTML CONSTRUIT (dist/client, build avant vitest en CI) :
// hreflang réciproques, canonique avec barre, aucun lien interne sans barre (base gelée qui ne
// peut que rétrécir), JSON-LD parsable. Nouveau fichier car aucun module ne lit dist/ entier.
import { describe, expect, it } from 'vitest';
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';

const CLIENT = join(process.cwd(), 'dist/client');
const SITE = 'https://taqinor.ma';

/** Base gelée : ne peut que descendre. Monter ce nombre exige de le justifier en revue. */
const LIENS_SANS_BARRE_MAX = 72;

export function pagesConstruites(racine = CLIENT): { route: string; html: string }[] {
  return (readdirSync(racine, { recursive: true }) as string[])
    .filter((f) => f.replace(/\\/g, '/').endsWith('index.html'))
    .map((f) => ({
      route: `/${f.replace(/\\/g, '/').replace(/index\.html$/, '')}`,
      html: readFileSync(join(racine, f), 'utf-8'),
    }));
}

export function alternates(html: string): Map<string, string> {
  const out = new Map<string, string>();
  for (const m of html.matchAll(/<link rel="alternate" hreflang="([^"]+)" href="([^"]+)"/g)) out.set(m[1], m[2]);
  return out;
}

export function liensSansBarre(html: string): string[] {
  const sansScripts = html.replace(/<script[\s\S]*?<\/script>/g, '');
  return [...sansScripts.matchAll(/<a\b[^>]*?\shref="(\/[^"#?]*)/g)]
    .map((m) => m[1])
    .filter((p) => !p.endsWith('/') && !p.slice(p.lastIndexOf('/') + 1).includes('.') && !p.startsWith('/api'));
}

export function jsonLdInvalides(html: string): string[] {
  const out: string[] = [];
  for (const m of html.matchAll(/<script type="application\/ld\+json"[^>]*>([\s\S]*?)<\/script>/g)) {
    try {
      JSON.parse(m[1]);
    } catch {
      out.push(m[1].slice(0, 80));
    }
  }
  return out;
}

/** WAUD93 — commentaires HTML hors <script>/<style>/<textarea>/<pre> (notes de dev livrées au public). */
export function commentairesHtml(html: string): string[] {
  const horsProteges = html.replace(/<(script|style|textarea|pre)\b[\s\S]*?<\/\1>/gi, '');
  return [...horsProteges.matchAll(/<!--[\s\S]*?-->/g)].map((m) => m[0].slice(0, 80));
}

export function nonReciproques(pages: { route: string; html: string }[]): string[] {
  const parUrl = new Map(pages.map((p) => [decodeURI(new URL(p.route, SITE).href), p]));
  const fautes: string[] = [];
  for (const p of pages) {
    const moi = decodeURI(new URL(p.route, SITE).href);
    for (const [langue, href] of alternates(p.html)) {
      if (langue === 'x-default') continue;
      const cible = parUrl.get(decodeURI(href));
      if (!cible) {
        // Page SSR ou absente du build : signalée seulement si elle devrait être statique.
        fautes.push(`${p.route} → ${langue} ${href} : introuvable`);
      } else if (![...alternates(cible.html).values()].some((h) => decodeURI(h) === moi)) {
        fautes.push(`${p.route} → ${langue} ${href} : pas de lien retour`);
      }
    }
  }
  return fautes;
}

const pages = existsSync(CLIENT) ? pagesConstruites() : [];

describe('WAUD59 — tech SEO du HTML construit', () => {
  it('le build est présent (jamais un faux vert silencieux)', () => {
    expect(pages.length, 'lancer « npm run build » avant vitest').toBeGreaterThan(100);
  });

  it('hreflang réciproques', () => {
    expect(nonReciproques(pages)).toEqual([]);
  });

  it('canonique = URL avec barre finale', () => {
    const fautes = pages.flatMap(({ route, html }) => {
      const c = html.match(/<link rel="canonical" href="([^"]+)"/)?.[1];
      return c && !new URL(c).pathname.endsWith('/') ? [`${route} → ${c}`] : [];
    });
    expect(fautes).toEqual([]);
  });

  it('aucun lien interne sans barre finale au-delà de la base gelée', () => {
    const fautes = pages.flatMap(({ route, html }) => liensSansBarre(html).map((l) => `${route} → ${decodeURI(l)}`));
    expect(fautes.slice(0, 20), `${fautes.length} liens`).toHaveLength(Math.min(fautes.length, 20));
    expect(fautes.length).toBeLessThanOrEqual(LIENS_SANS_BARRE_MAX);
  });

  it('WAUD93 — aucun commentaire HTML (notes de développement) dans le HTML construit', () => {
    const fautes = pages.flatMap(({ route, html }) => commentairesHtml(html).map((c) => `${route}: ${c}`));
    expect(fautes.slice(0, 10), `${fautes.length} commentaires`).toEqual([]);
  });

  it('JSON-LD parsable partout', () => {
    expect(pages.flatMap(({ route, html }) => jsonLdInvalides(html).map((j) => `${route}: ${j}`))).toEqual([]);
  });
});

describe('WAUD59 — test du test : casser une règle fait rougir la garde', () => {
  const A = `<link rel="alternate" hreflang="fr" href="${SITE}/x/" /><link rel="alternate" hreflang="en" href="${SITE}/en/x/" />`;
  it('hreflang sans retour détecté', () => {
    const fautes = nonReciproques([
      { route: '/x/', html: A },
      { route: '/en/x/', html: `<link rel="alternate" hreflang="fr" href="${SITE}/autre/" />` },
      { route: '/autre/', html: '' },
    ]);
    expect(fautes.join()).toMatch(/pas de lien retour|introuvable/);
  });
  it('lien sans barre et JSON-LD cassé détectés ; fichier et ancre tolérés', () => {
    expect(liensSansBarre('<a href="/faq">x</a><a href="/faq/">y</a><a href="/rss.xml">z</a>')).toEqual(['/faq']);
    expect(jsonLdInvalides('<script type="application/ld+json">{oups</script>')).toHaveLength(1);
  });
  it('WAUD93 — commentaire HTML détecté ; celui d’un script toléré', () => {
    expect(commentairesHtml('<p>a</p><!-- W215 — note --><b>b</b>')).toHaveLength(1);
    expect(commentairesHtml('<script>var s = "<!-- x -->";</script><p>ok</p>')).toEqual([]);
  });
});
