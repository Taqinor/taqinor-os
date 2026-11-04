// WJ18 — Performance mobile <3s (Android milieu de gamme / 3G) : le 3D (Three.js
// + MapLibre) ne doit JAMAIS faire partie du bundle client initial des deux
// pages du parcours — seulement des <script> légers (logique pure / DOM),
// avec le moteur 3D chargé par import() dynamique, gated par tap / scroll /
// reduced-motion / Save-Data (WJ27, réutilisé tel quel par WJ2). Lecture
// SOURCE en texte (même convention que quoteCtaWJ36.test.ts) : le vrai poids
// de bundle est vérifié par le job CI web-build-test (Lighthouse), ce test
// verrouille le CONTRAT source qui le garantit (aucun import statique lourd).
import { describe, expect, it } from 'vitest';
import { readdirSync, readFileSync } from 'node:fs';
import { lireSourceTunnel } from './astroBlocsHelper';
import { fileURLToPath } from 'node:url';
import { lirePageProposition } from './astroBlocsHelper';

const root = (rel: string) => fileURLToPath(new URL(rel, import.meta.url));
const read = (rel: string) => lireSourceTunnel(root(rel));

const MON_TOIT = read('../src/pages/devis/mon-toit.astro');
const PROPOSITION = lirePageProposition();
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
    // RWEB17-M14 — l'aperçu 3D vit dans lib/tunnel/carte.ts : même import() dynamique, chemin du module.
    expect(MON_TOIT).toContain("import('../proposition')");
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
    // RWEB17-M14 — la page fournit le chargeur dynamique à lib/tunnel/carte.ts, qui l'attend au boot.
    expect(MON_TOIT).toContain("captureBoot: () => import('../../scripts/roofPro11/captureBoot')");
    expect(MON_TOIT).toContain('await config.chargeurs.captureBoot()');
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

describe('WAUD8 — aucune animation infinie qui force une peinture à chaque image', () => {
  // Liste d'exceptions EXPLICITE : vide. Une entrée ici doit être justifiée.
  const EXCEPTIONS: string[] = [];
  const SRC = fileURLToPath(new URL('../src/', import.meta.url));
  const fichiers = (readdirSync(SRC, { recursive: true }) as string[])
    .filter((f) => /\.(css|astro)$/.test(f))
    .map((f) => ({ f, code: readFileSync(SRC + f, 'utf-8') }));

  /** Corps d'un @keyframes (accolades équilibrées). */
  function corpsKeyframes(code: string, nom: string): string | null {
    const debut = code.search(new RegExp(`@keyframes\\s+${nom}\\b`));
    if (debut < 0) return null;
    let i = code.indexOf('{', debut);
    const ouverture = i;
    let n = 0;
    for (; i < code.length; i += 1) {
      if (code[i] === '{') n += 1;
      if (code[i] === '}' && --n === 0) return code.slice(ouverture, i + 1);
    }
    return null;
  }

  it('filter, box-shadow et background-position jamais animés en boucle', () => {
    const toutes = fichiers.map((x) => x.code).join('\n');
    const noms = new Set<string>();
    for (const m of toutes.matchAll(/animation\s*:\s*([^;}]*\binfinite\b[^;}]*)/g)) {
      for (const mot of m[1].split(/\s+/)) {
        if (/^[a-zA-Z][\w-]*$/.test(mot) && corpsKeyframes(toutes, mot)) noms.add(mot);
      }
    }
    expect(noms.size).toBeGreaterThan(0);
    const fautives = [...noms].filter((nom) => {
      if (EXCEPTIONS.includes(nom)) return false;
      return /(^|[\s{;])(-webkit-)?(filter|box-shadow|background-position)\s*:/.test(corpsKeyframes(toutes, nom) ?? '');
    });
    expect(fautives).toEqual([]);
  });

  it('logo et squelette du tunnel : halos composités, reduced-motion respecté', () => {
    const logo = readFileSync(root('../src/components/Logo.astro'), 'utf-8');
    expect(logo).toMatch(/prefers-reduced-motion: no-preference\)\s*\{\s*\.sun-wrap::after/);
    const css = readFileSync(root('../src/styles/mon-toit-page.css'), 'utf-8');
    expect(css).toMatch(/prefers-reduced-motion: no-preference\)\s*\{\s*\.mt-skeleton-shimmer::after/);
  });
});

describe('WAUD78 — la carte attend un geste à l’étape 0 (facultative)', () => {
  it('les 3 tunnels portent la façade, à côté du conteneur de carte', () => {
    for (const p of ['../src/pages/devis/mon-toit.astro', '../src/pages/en/devis/mon-toit.astro', '../src/pages/ar/devis/mon-toit.astro']) {
      expect(readFileSync(root(p), 'utf-8')).toContain('id="mt-map-facade"');
    }
  });
  it('carte et Three restent des imports dynamiques dans les modules du tunnel', () => {
    for (const p of ['../src/lib/tunnel/carte.ts', '../src/lib/tunnel/parcours.ts']) {
      expect(staticValueImports(readFileSync(root(p), 'utf-8')).filter((m) => /maplibre|three|roofPro11/.test(m))).toEqual([]);
    }
  });
});

describe('WAUD54 — vidéos d’ambiance : ordinateur + 4G seulement', () => {
  const ok = { largeur: 1440, effectiveType: '4g', saveData: false, motionOk: true };

  it('ordinateur en 4G (ou réseau inconnu) : la vidéo peut jouer', async () => {
    const { videoAmbianceAutorisee } = await import('../src/lib/videoAmbiance');
    expect(videoAmbianceAutorisee(ok)).toBe(true);
    expect(videoAmbianceAutorisee({ ...ok, effectiveType: undefined })).toBe(true);
    expect(videoAmbianceAutorisee({ ...ok, largeur: 1024 })).toBe(true);
  });

  it('mobile, 3G, économie de données ou reduced-motion : jamais', async () => {
    const { videoAmbianceAutorisee } = await import('../src/lib/videoAmbiance');
    expect(videoAmbianceAutorisee({ ...ok, largeur: 1023 })).toBe(false);
    expect(videoAmbianceAutorisee({ ...ok, largeur: 390 })).toBe(false);
    expect(videoAmbianceAutorisee({ ...ok, effectiveType: '3g' })).toBe(false);
    expect(videoAmbianceAutorisee({ ...ok, effectiveType: 'slow-2g' })).toBe(false);
    expect(videoAmbianceAutorisee({ ...ok, saveData: true })).toBe(false);
    expect(videoAmbianceAutorisee({ ...ok, motionOk: false })).toBe(false);
  });

  it('le héros et le teaser passent tous deux par la garde (affiche fixe sinon)', () => {
    for (const p of ['../src/components/home/HeroVideoScript.astro', '../src/components/VideoChantier.astro']) {
      const src = readFileSync(root(p), 'utf-8');
      expect(src).toContain('videoAmbianceDuNavigateur()');
      expect(src).not.toContain('navigator.connection');
    }
  });
});
