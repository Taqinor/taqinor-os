// Garde-fous de l'ESTIMATEUR DE TOITURE (preview privé /preview/toiture) :
//  1. route privée (noindex, sous-dossier, exclue du sitemap) ;
//  2. MapLibre chargé PARESSEUSEMENT — jamais dans le bundle d'une autre page ;
//  3. capture du lead RÉUTILISÉE telle quelle (seuil 1 000 MAD, consentement,
//     webhook, CAPI inchangés) — l'outil ne fait que pré-remplir ;
//  4. la route d'estimation ne touche AUCUNE donnée de lead.
import { describe, expect, it } from 'vitest';
import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const read = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');
const srcDir = fileURLToPath(new URL('../src', import.meta.url));

function walk(dir: string, out: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    const full = `${dir}/${name}`;
    if (statSync(full).isDirectory()) walk(full, out);
    else out.push(full);
  }
  return out;
}

describe('estimateur — route privée, jamais indexée', () => {
  it('la page /preview/toiture est noindex', () => {
    expect(read('../src/pages/preview/toiture.astro')).toContain('noindex={true}');
  });

  it('vit dans /preview/ (sous-dossier) → comptage de pages top-level inchangé', () => {
    expect(existsSync(fileURLToPath(new URL('../src/pages/preview/toiture.astro', import.meta.url)))).toBe(true);
    expect(existsSync(fileURLToPath(new URL('../src/pages/toiture.astro', import.meta.url)))).toBe(false);
  });

  it('le filtre sitemap exclut bien /preview/ (donc /preview/toiture)', () => {
    const filterLine = read('../astro.config.mjs')
      .split('\n')
      .find((l) => l.includes('filter:')) ?? '';
    expect(filterLine).toContain('preview');
  });

  it("aucune page publique ne monte l'estimateur", () => {
    for (const p of ['index', 'résidentiel', 'professionnel', 'contact', 'équipement', 'loi-82-21', 'regularization-article-33']) {
      expect(read(`../src/pages/${p}.astro`)).not.toContain('roof-tool');
    }
  });
});

describe('estimateur — MapLibre chargé paresseusement (aucun autre bundle touché)', () => {
  it('MapLibre n’est IMPORTÉ que dans le module d’outil chargé à la demande', () => {
    // On cherche les vrais imports de module (pas une classe CSS .maplibregl-map,
    // qui n'embarque rien) : `from 'maplibre…` ou `import 'maplibre…`.
    const importsMaplibre = (s: string) => /(?:from|import)\s*\(?\s*['"]maplibre-gl/.test(s);
    const offenders = walk(srcDir)
      .filter((f) => /\.(ts|tsx|js|astro)$/.test(f))
      .filter((f) => importsMaplibre(readFileSync(f, 'utf-8')))
      .map((f) => f.replace(srcDir, 'src').replaceAll('\\', '/'))
      .sort();
    // Les DEUX outils (2D + variante 3D), et eux seuls, importent MapLibre —
    // tous deux chargés à la demande, jamais dans le bundle d'une autre page.
    expect(offenders).toEqual(['src/scripts/roof-tool-3d.ts', 'src/scripts/roof-tool.ts']);
  });

  it('la page charge l’outil par import() dynamique, pas en statique', () => {
    const page = read('../src/pages/preview/toiture.astro');
    expect(page).toContain("import('../../scripts/roof-tool");
    expect(page).not.toMatch(/import\s+\w+\s+from\s+['"]maplibre/);
  });

  it('le module d’outil importe MapLibre (et sa CSS) en interne', () => {
    const tool = read('../src/scripts/roof-tool.ts');
    expect(tool).toContain("from 'maplibre-gl'");
    expect(tool).toContain("maplibre-gl/dist/maplibre-gl.css");
  });
});

describe('estimateur — capture du lead RÉUTILISÉE, plomberie intacte', () => {
  it('la page réutilise DiagnosticFormEnriched et ne poste aucun lead elle-même', () => {
    const page = read('../src/pages/preview/toiture.astro');
    expect(page).toContain('DiagnosticFormEnriched');
    // L'outil n'appelle JAMAIS les endpoints de lead directement : seul le
    // formulaire réutilisé poste le lead. (Le commentaire d'en-tête peut citer
    // /api/preview-lead pour décrire le flux — on vérifie l'absence d'un fetch.)
    expect(page).not.toContain("fetch('/api/preview-lead'");
    expect(page).not.toContain("fetch('/api/simulate'");
  });

  it('le pré-remplissage passe par les champs du formulaire (jamais par un lead bis)', () => {
    const tool = read('../src/scripts/roof-tool.ts');
    // Écrit dans les champs existants du diagnostic enrichi…
    expect(tool).toContain("'lf-area'");
    expect(tool).toContain("'lf-orient'");
    expect(tool).toContain("'lf-kwc-est'");
    // …et ne poste lui-même AUCUN lead.
    expect(tool).not.toContain('/api/preview-lead');
    expect(tool).not.toContain('/api/simulate');
  });

  it('seuil + consentement + CAPI inchangés (preview-lead poste toujours le record de base au CAPI)', () => {
    const ep = read('../src/pages/api/preview-lead.ts');
    expect(ep).toContain('fireCapi(baseRecord'); // signal publicitaire identique
    expect(ep).toContain('cleanEnrichment');
    const enr = read('../src/components/DiagnosticFormEnriched.astro');
    expect(enr).toContain('name="consent" required'); // consentement toujours requis
    expect(enr).toContain("fetch('/api/preview-lead'");
  });

  it("le champ estimatedKwc reste hors du formulaire LIVE (aucune fuite en production)", () => {
    expect(read('../src/components/DiagnosticForm.astro')).not.toContain('estimatedKwc');
    // Présent en revanche dans la variante enrichie (pré-remplie par l'outil).
    expect(read('../src/components/DiagnosticFormEnriched.astro')).toContain('name="estimatedKwc"');
  });
});

describe('estimateur — cycle de vie carte : init unique, repli seulement sur échec réel', () => {
  it('/api/roof-config lit la clé RUNTIME ET la clé de BUILD (corrige le bug variable de build)', () => {
    const ep = read('../src/pages/api/roof-config.ts');
    expect(ep).toContain('resolveMaptilerKey');
    expect(ep).toContain('cf.env'); // source runtime
    expect(ep).toContain('import.meta.env.PUBLIC_MAPTILER_KEY'); // source build (inlinée par Vite)
    // Pas de cache : un available:false périmé ne doit pas masquer la carte.
    expect(ep).toContain("'cache-control': 'no-store'");
  });

  it('la carte s’initialise UNE seule fois (garde-fou booted)', () => {
    const tool = read('../src/scripts/roof-tool.ts');
    expect(tool).toMatch(/let booted = false/);
    expect(tool).toMatch(/if \(booted\) return/);
  });

  it('les erreurs MapLibre non fatales sont journalisées, jamais bloquantes', () => {
    const tool = read('../src/scripts/roof-tool.ts');
    expect(tool).toContain("map.on('error'");
    // L’erreur ne déclenche aucun repli ni teardown.
    expect(tool).not.toMatch(/map\.on\('error'[\s\S]{0,400}showFallback/);
    expect(tool).not.toMatch(/map\.on\('error'[\s\S]{0,400}\.remove\(\)/);
  });

  it('une carte créée n’est jamais masquée : le repli n’arrive que si onReady n’a pas signalé', () => {
    const tool = read('../src/scripts/roof-tool.ts');
    expect(tool).toContain('opts.onReady?.()'); // signale dès la création
    const page = read('../src/pages/preview/toiture.astro');
    expect(page).toContain('mapCreated');
    expect(page).toMatch(/if \(!mapCreated\)[\s\S]{0,80}showFallback/);
  });
});

describe('estimateur 3D — variante privée, parallèle, sans toucher la 2D', () => {
  const page3d = '../src/pages/preview/toiture-3d.astro';
  const tool3d = '../src/scripts/roof-tool-3d.ts';

  it('la page /preview/toiture-3d est noindex et vit dans /preview/ (sous-dossier)', () => {
    expect(read(page3d)).toContain('noindex={true}');
    expect(existsSync(fileURLToPath(new URL(page3d, import.meta.url)))).toBe(true);
    expect(existsSync(fileURLToPath(new URL('../src/pages/toiture-3d.astro', import.meta.url)))).toBe(false);
  });

  it('la 2D /preview/toiture reste strictement inchangée (ne mentionne jamais la 3D)', () => {
    const page2d = read('../src/pages/preview/toiture.astro');
    expect(page2d).not.toContain('toiture-3d');
    expect(page2d).not.toContain('roof-tool-3d');
    // L'outil 2D ne référence pas la variante 3D non plus.
    expect(read('../src/scripts/roof-tool.ts')).not.toContain('roof-tool-3d');
  });

  it('la page 3D charge l’outil par import() dynamique, pas en statique', () => {
    const page = read(page3d);
    expect(page).toContain("import('../../scripts/roof-tool-3d");
    expect(page).not.toMatch(/import\s+\w+\s+from\s+['"]maplibre/);
  });

  it('le module 3D fait la 3D en MapLibre NATIF — aucune dépendance ajoutée (pas de Three.js)', () => {
    const tool = read(tool3d);
    expect(tool).toContain("from 'maplibre-gl'");
    expect(tool).toContain('fill-extrusion'); // massing natif MapLibre
    expect(tool).not.toMatch(/from\s+['"]three/); // aucun import Three.js
  });

  it('la 3D RÉUTILISE le même calcul et le même lead (jamais de fork)', () => {
    const tool = read(tool3d);
    // Calcul partagé : importe la géométrie testée, n'en réimplémente pas.
    expect(tool).toContain("from '../lib/roof'");
    expect(tool).toContain('layoutPanels');
    // Production : MÊME proxy serveur, jamais PVGIS direct.
    expect(tool).toContain("'/api/roof-estimate'");
    expect(tool).not.toContain('re.jrc.ec.europa.eu');
    // Lead : pré-remplit les MÊMES champs, ne poste aucun lead lui-même.
    expect(tool).toContain("'lf-area'");
    expect(tool).toContain("'lf-orient'");
    expect(tool).toContain("'lf-kwc-est'");
    expect(tool).not.toContain('/api/preview-lead');
    expect(tool).not.toContain('/api/simulate');
    // La page réutilise le formulaire de production, sans poster de lead.
    const page = read(page3d);
    expect(page).toContain('DiagnosticFormEnriched');
    expect(page).not.toContain("fetch('/api/preview-lead'");
  });

  it('prefers-reduced-motion : bascule 3D instantanée, aucune animation auto', () => {
    const tool = read(tool3d);
    expect(tool).toContain('opts.reducedMotion'); // chemin sans animation
    expect(tool).toContain('map.jumpTo'); // bascule instantanée si réduit
    // Aucune rotation automatique continue.
    expect(tool).not.toContain('rotateTo');
    expect(tool).not.toMatch(/setInterval|requestAnimationFrame/);
  });

  it('repli gracieux : WebGL absent → l’outil lève (la page bascule sur le repli)', () => {
    const tool = read(tool3d);
    expect(tool).toContain('webgl');
    expect(tool).toMatch(/throw new Error/);
    const page = read(page3d);
    expect(page).toContain('mapCreated');
    expect(page).toMatch(/if \(!mapCreated\)[\s\S]{0,80}showFallback/);
  });

  it('aucune page publique ne monte l’estimateur 3D', () => {
    for (const p of ['index', 'résidentiel', 'professionnel', 'contact', 'équipement', 'loi-82-21', 'regularization-article-33']) {
      expect(read(`../src/pages/${p}.astro`)).not.toContain('roof-tool-3d');
    }
  });
});

describe('estimateur — la route d’estimation ne touche aucune donnée de lead', () => {
  it('/api/roof-estimate n’importe ni ne référence la plomberie de lead', () => {
    const ep = read('../src/pages/api/roof-estimate.ts');
    for (const forbidden of ['validateLead', 'forwardLead', 'fireCapi', 'buildLeadRecord', 'cleanEnrichment', 'LEAD_WEBHOOK', 'CAPI']) {
      expect(ep, `roof-estimate ne doit pas connaître ${forbidden}`).not.toContain(forbidden);
    }
  });

  it('PVGIS est appelé côté serveur uniquement (la page n’y touche jamais)', () => {
    expect(read('../src/pages/preview/toiture.astro')).not.toContain('pvgis');
    expect(read('../src/scripts/roof-tool.ts')).not.toContain('re.jrc.ec.europa.eu');
    expect(read('../src/lib/roofEstimate.ts')).toContain('re.jrc.ec.europa.eu');
  });
});
