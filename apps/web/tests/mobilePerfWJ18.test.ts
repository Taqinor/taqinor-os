// WJ18 — Performance mobile <3s (Android milieu de gamme / 3G) : le 3D (Three.js
// + MapLibre) ne doit JAMAIS faire partie du bundle client initial des deux
// pages du parcours — seulement des <script> légers (logique pure / DOM),
// avec le moteur 3D chargé par import() dynamique, gated par tap / scroll /
// reduced-motion / Save-Data (WJ27, réutilisé tel quel par WJ2). Lecture
// SOURCE en texte (même convention que quoteCtaWJ36.test.ts) : le vrai poids
// de bundle est vérifié par le job CI web-build-test (Lighthouse), ce test
// verrouille le CONTRAT source qui le garantit (aucun import statique lourd).
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const root = (rel: string) => fileURLToPath(new URL(rel, import.meta.url));
const read = (rel: string) => readFileSync(root(rel), 'utf-8');

const MON_TOIT = read('../src/pages/devis/mon-toit.astro');
const PROPOSITION = read('../src/pages/proposition/[token].astro');
const VIEWER_ONLY = read('../src/scripts/roofPro11/viewerOnly.ts');

/** Imports statiques top-niveau d'un bloc <script> Astro (hors `import type`). */
function staticValueImports(src: string): string[] {
  return [...src.matchAll(/^\s*import\s+(?!type\s)[^;]*from\s+'([^']+)';?/gm)].map((m) => m[1]);
}

describe('WJ18 — mon-toit.astro : le 3D (WJ2) n’est JAMAIS statiquement importé', () => {
  const imports = staticValueImports(MON_TOIT);

  it('aucun import statique ne référence three / roofPro11/viewerOnly / roof-tool-pro11', () => {
    for (const spec of imports) {
      expect(spec).not.toMatch(/three/i);
      expect(spec).not.toMatch(/viewerOnly/);
      expect(spec).not.toMatch(/roof-tool-pro11/);
    }
  });

  it('le moteur 3D (WJ2) est chargé par import() dynamique, uniquement au tap explicite', () => {
    expect(MON_TOIT).toContain("import('../../lib/proposition')");
    expect(MON_TOIT).toContain("import('../../scripts/roofPro11/viewerOnly')");
    // Le tap explicite déclenche startPanels3d — jamais un scroll/auto-preload
    // pour le bloc panneaux 3D (budget perf plus serré qu'une proposition déjà
    // ouverte avec intention d'achat) ; aucun IntersectionObserver ne pilote WJ2.
    expect(MON_TOIT).toContain("panels3dStart?.addEventListener('click'");
    const wj2Block = MON_TOIT.slice(MON_TOIT.indexOf('WJ2 : « voir les panneaux'), MON_TOIT.indexOf('WJ4 : validation'));
    expect(wj2Block).not.toContain('IntersectionObserver');
  });

  it('la carte (MapLibre) est aussi chargée par import() dynamique (roofPro11/captureBoot — WJ47)', () => {
    // WJ47 : la capture importe directement roofPro11/captureBoot (qui charge MapLibre)
    // au lieu de roof-tool-pro11.ts, pour ne PAS embarquer Three.js dans le bundle capture.
    expect(MON_TOIT).toContain("await import('../../scripts/roofPro11/captureBoot')");
  });
});

describe('WJ18 — [token].astro : la visionneuse 3D (WJ25/27) reste lazy, jamais statique', () => {
  const imports = staticValueImports(PROPOSITION);

  it('aucun import statique ne référence three / viewerOnly', () => {
    for (const spec of imports) {
      expect(spec).not.toMatch(/three/i);
      expect(spec).not.toMatch(/viewerOnly/);
    }
  });

  it('la visionneuse 3D charge par import() dynamique, gated scroll (IO) ou tap (reduced-motion/Save-Data)', () => {
    expect(PROPOSITION).toContain("await import('../../scripts/roofPro11/viewerOnly')");
    expect(PROPOSITION).toContain('IntersectionObserver');
    expect(PROPOSITION).toContain("startBtn?.addEventListener('click'");
  });

  it('le shell rend côté serveur (prerender=false, SSR) — le contenu n’attend jamais l’hydratation 3D', () => {
    expect(PROPOSITION).toContain('export const prerender = false;');
    // Les données (options, chiffres, hero) sont résolues dans le frontmatter
    // (fetch serveur), pas dans un effet client — le HTML complet part déjà rempli.
    expect(PROPOSITION).toContain('await fetch(proposalEndpoint(API_BASE, token)');
  });
});

describe('WJ18 — viewerOnly.ts : le budget bas de gamme reste appliqué (partagé WJ2 + WJ27)', () => {
  it('DPR plafonné et anti-aliasing coupé sur appareil bas de gamme', () => {
    expect(VIEWER_ONLY).toContain('export function viewerDprCap');
    expect(VIEWER_ONLY).toContain('lowEnd ? 1.5 : 2');
  });

  it('rendu à la demande (aucune boucle RAF permanente) — coût CPU/batterie mobile minimal', () => {
    expect(VIEWER_ONLY).toContain('Rendu À LA DEMANDE');
    expect(VIEWER_ONLY).not.toMatch(/setInterval/);
  });
});
