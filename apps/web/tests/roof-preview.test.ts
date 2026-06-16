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
    // Les SIX outils (2D + 3D volumes + 3D racks + 3D haute fidélité + estimateur
    // facture pro-3 + pro-4 cerveau V2), et eux seuls, importent MapLibre — tous
    // chargés à la demande.
    expect(offenders).toEqual([
      'src/scripts/roof-tool-3d.ts',
      'src/scripts/roof-tool-pro.ts',
      'src/scripts/roof-tool-pro2.ts',
      'src/scripts/roof-tool-pro3.ts',
      'src/scripts/roof-tool-pro4.ts',
      'src/scripts/roof-tool.ts',
    ]);
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

describe('estimateur 3D RÉALISTE (pro) — Three.js isolé, parallèle, sans toucher le reste', () => {
  const pagePro = '../src/pages/preview/toiture-3d-pro.astro';
  const toolPro = '../src/scripts/roof-tool-pro.ts';

  it('la page /preview/toiture-3d-pro est noindex et vit dans /preview/ (sous-dossier)', () => {
    expect(read(pagePro)).toContain('noindex={true}');
    expect(existsSync(fileURLToPath(new URL(pagePro, import.meta.url)))).toBe(true);
    expect(existsSync(fileURLToPath(new URL('../src/pages/toiture-3d-pro.astro', import.meta.url)))).toBe(false);
  });

  it('le filtre sitemap exclut /preview/ (donc aussi /preview/toiture-3d-pro)', () => {
    const filterLine = read('../astro.config.mjs')
      .split('\n')
      .find((l) => l.includes('filter:')) ?? '';
    expect(filterLine).toContain('preview');
  });

  it('la 2D et la 3D « volumes » restent inchangées (n’évoquent jamais la pro)', () => {
    for (const f of [
      '../src/pages/preview/toiture.astro',
      '../src/scripts/roof-tool.ts',
      '../src/pages/preview/toiture-3d.astro',
      '../src/scripts/roof-tool-3d.ts',
    ]) {
      expect(read(f)).not.toContain('toiture-3d-pro');
      expect(read(f)).not.toContain('roof-tool-pro');
      // Aucun de ces fichiers n'importe Three.js.
      expect(read(f)).not.toMatch(/from\s+['"]three['"]/);
    }
  });

  it('Three.js n’est IMPORTÉ que dans le module pro (jamais ailleurs dans src)', () => {
    const importsThree = (s: string) => /(?:from|import)\s*\(?\s*['"]three['"]/.test(s);
    const offenders = walk(srcDir)
      .filter((f) => /\.(ts|tsx|js|astro)$/.test(f))
      .filter((f) => importsThree(readFileSync(f, 'utf-8')))
      .map((f) => f.replace(srcDir, 'src').replaceAll('\\', '/'))
      .sort();
    expect(offenders).toEqual([
      'src/scripts/roof-tool-pro.ts',
      'src/scripts/roof-tool-pro2.ts',
      'src/scripts/roof-tool-pro3.ts',
      'src/scripts/roof-tool-pro4.ts',
    ]);
  });

  it('Three.js est la SEULE dépendance ajoutée (pas de threebox ni @types/three)', () => {
    const pkg = JSON.parse(read('../package.json')) as {
      dependencies?: Record<string, string>;
      devDependencies?: Record<string, string>;
    };
    expect(pkg.dependencies?.three).toBeTruthy();
    const all = { ...pkg.dependencies, ...pkg.devDependencies };
    expect(all['threebox-plugin']).toBeUndefined();
    expect(all.threebox).toBeUndefined();
    expect(all['@types/three']).toBeUndefined();
  });

  it('la page pro charge l’outil par import() dynamique, pas en statique', () => {
    const page = read(pagePro);
    expect(page).toContain("import('../../scripts/roof-tool-pro");
    expect(page).not.toMatch(/import\s+\w+\s+from\s+['"]maplibre/);
    expect(page).not.toMatch(/import\s+.*\s+from\s+['"]three/);
  });

  it('le module pro fait la 3D réaliste via une COUCHE PERSONNALISÉE MapLibre + Three', () => {
    const tool = read(toolPro);
    expect(tool).toContain("from 'maplibre-gl'");
    expect(tool).toContain("import * as THREE from 'three'");
    expect(tool).toContain("type: 'custom'"); // couche personnalisée
    expect(tool).toContain('InstancedMesh'); // panneaux/châssis répétés performants
    expect(tool).toContain('mainMatrix'); // pont projection MapLibre ↔ Three
  });

  it('la pro RÉUTILISE le calepinage espacé et le même lead (jamais de fork)', () => {
    const tool = read(toolPro);
    // Calepinage « pro » testé, réutilise roof.ts (non modifié).
    expect(tool).toContain("from '../lib/roofPro'");
    expect(tool).toContain('layoutProRows');
    // Production : MÊME proxy serveur, jamais PVGIS direct.
    expect(tool).toContain("'/api/roof-estimate'");
    expect(tool).not.toContain('re.jrc.ec.europa.eu');
    // Lead : pré-remplit les MÊMES champs, ne poste aucun lead lui-même.
    expect(tool).toContain("'lf-area'");
    expect(tool).toContain("'lf-orient'");
    expect(tool).toContain("'lf-kwc-est'");
    expect(tool).not.toContain('/api/preview-lead');
    expect(tool).not.toContain('/api/simulate');
    const page = read(pagePro);
    expect(page).toContain('DiagnosticFormEnriched');
    expect(page).not.toContain("fetch('/api/preview-lead'");
  });

  it('roofPro NE modifie PAS roof.ts : il l’importe (aire, point-dans-polygone, kWc)', () => {
    const lib = read('../src/lib/roofPro.ts');
    expect(lib).toContain("from './roof'");
    expect(lib).toContain('geodesicAreaM2');
    expect(lib).toContain('kwcFromPanelCount');
  });

  it('prefers-reduced-motion : bascule 3D instantanée, aucune animation/rendu auto', () => {
    const tool = read(toolPro);
    expect(tool).toContain('opts.reducedMotion');
    expect(tool).toContain('map.jumpTo');
    // Pas de boucle de rendu continue ni de rotation automatique.
    expect(tool).not.toContain('rotateTo');
    expect(tool).not.toMatch(/setInterval|requestAnimationFrame/);
    // triggerRepaint n'est JAMAIS appelé dans la méthode render() de la couche
    // (sinon boucle continue) — on le commente explicitement.
    expect(tool).not.toMatch(/render\([^)]*\)\s*\{[\s\S]{0,400}triggerRepaint/);
  });

  it('repli gracieux : WebGL absent → l’outil lève (la page bascule sur le repli)', () => {
    const tool = read(toolPro);
    expect(tool).toContain('webgl');
    expect(tool).toMatch(/throw new Error/);
    const page = read(pagePro);
    expect(page).toContain('mapCreated');
    expect(page).toMatch(/if \(!mapCreated\)[\s\S]{0,80}showFallback/);
  });

  it('aucune page publique ne monte l’estimateur pro (ni Three.js)', () => {
    for (const p of ['index', 'résidentiel', 'professionnel', 'contact', 'équipement', 'loi-82-21', 'regularization-article-33']) {
      const page = read(`../src/pages/${p}.astro`);
      expect(page).not.toContain('roof-tool-pro');
      expect(page).not.toMatch(/from\s+['"]three/);
    }
  });
});

describe('estimateur 3D HAUTE FIDÉLITÉ (pro 2) — vrais panneaux, vrai sud, vrai soleil', () => {
  const page2 = '../src/pages/preview/toiture-3d-pro-2.astro';
  const tool2 = '../src/scripts/roof-tool-pro2.ts';
  const lib2 = '../src/lib/roofPro2.ts';

  it('la page /preview/toiture-3d-pro-2 est noindex et vit dans /preview/ (sous-dossier)', () => {
    expect(read(page2)).toContain('noindex={true}');
    expect(existsSync(fileURLToPath(new URL(page2, import.meta.url)))).toBe(true);
    expect(existsSync(fileURLToPath(new URL('../src/pages/toiture-3d-pro-2.astro', import.meta.url)))).toBe(false);
  });

  it('le filtre sitemap exclut /preview/ (donc aussi /preview/toiture-3d-pro-2)', () => {
    const filterLine = read('../astro.config.mjs')
      .split('\n')
      .find((l) => l.includes('filter:')) ?? '';
    expect(filterLine).toContain('preview');
  });

  it('les previews existantes (2D, 3D volumes, 3D racks) restent inchangées', () => {
    for (const f of [
      '../src/pages/preview/toiture.astro',
      '../src/scripts/roof-tool.ts',
      '../src/pages/preview/toiture-3d.astro',
      '../src/scripts/roof-tool-3d.ts',
      '../src/pages/preview/toiture-3d-pro.astro',
      '../src/scripts/roof-tool-pro.ts',
      '../src/lib/roofPro.ts',
    ]) {
      expect(read(f)).not.toContain('toiture-3d-pro-2');
      expect(read(f)).not.toContain('roof-tool-pro2');
      expect(read(f)).not.toContain('roofPro2');
    }
  });

  it('aucune NOUVELLE dépendance : Three.js déjà présent, rien d’autre ajouté', () => {
    const pkg = JSON.parse(read('../package.json')) as {
      dependencies?: Record<string, string>;
      devDependencies?: Record<string, string>;
    };
    expect(pkg.dependencies?.three).toBeTruthy();
    const all = { ...pkg.dependencies, ...pkg.devDependencies };
    expect(all.threebox).toBeUndefined();
    expect(all['@types/three']).toBeUndefined();
  });

  it('la page pro 2 charge l’outil par import() dynamique, pas en statique', () => {
    const page = read(page2);
    expect(page).toContain("import('../../scripts/roof-tool-pro2");
    expect(page).not.toMatch(/import\s+\w+\s+from\s+['"]maplibre/);
    expect(page).not.toMatch(/import\s+.*\s+from\s+['"]three/);
  });

  it('le module pro 2 : couche perso MapLibre + Three, vrai panneau, vrai soleil, ombres', () => {
    const tool = read(tool2);
    expect(tool).toContain("import * as THREE from 'three'");
    expect(tool).toContain("type: 'custom'");
    expect(tool).toContain('InstancedMesh');
    expect(tool).toContain('mainMatrix');
    // Vraies ombres portées.
    expect(tool).toContain('castShadow');
    expect(tool).toContain('shadowMap.enabled');
    // Boussole (cap réel visible).
    expect(tool).toContain('getBearing');
  });

  it('la pro 2 RÉUTILISE le calepinage 720 W et le même lead (jamais de fork)', () => {
    const tool = read(tool2);
    expect(tool).toContain("from '../lib/roofPro2'");
    expect(tool).toContain('layoutProRows2');
    expect(tool).toContain("'/api/roof-estimate'");
    expect(tool).not.toContain('re.jrc.ec.europa.eu');
    expect(tool).toContain("'lf-area'");
    expect(tool).toContain("'lf-orient'");
    expect(tool).toContain("'lf-kwc-est'");
    expect(tool).not.toContain('/api/preview-lead');
    expect(tool).not.toContain('/api/simulate');
    const page = read(page2);
    expect(page).toContain('DiagnosticFormEnriched');
    expect(page).not.toContain("fetch('/api/preview-lead'");
  });

  it('roofPro2 réutilise roof.ts (aire, point-dans-polygone) sans le modifier', () => {
    const lib = read(lib2);
    expect(lib).toContain("from './roof'");
    expect(lib).toContain('geodesicAreaM2');
    // Vrai panneau 720 W + géométrie solaire d'espacement.
    expect(lib).toContain('2.384');
    expect(lib).toContain('1.303');
    expect(lib).toContain('720');
    expect(lib).toContain('designSunElevationDeg');
  });

  it('prefers-reduced-motion : bascule instantanée, aucun rendu/rotation auto', () => {
    const tool = read(tool2);
    expect(tool).toContain('opts.reducedMotion');
    expect(tool).toContain('map.jumpTo');
    expect(tool).not.toContain('rotateTo');
    expect(tool).not.toMatch(/setInterval|requestAnimationFrame/);
    expect(tool).not.toMatch(/render\([^)]*\)\s*\{[\s\S]{0,400}triggerRepaint/);
  });

  it('repli gracieux : WebGL absent → l’outil lève (la page bascule sur le repli)', () => {
    const tool = read(tool2);
    expect(tool).toContain('webgl');
    expect(tool).toMatch(/throw new Error/);
    const page = read(page2);
    expect(page).toContain('mapCreated');
    expect(page).toMatch(/if \(!mapCreated\)[\s\S]{0,80}showFallback/);
  });

  it('aucune page publique ne monte l’estimateur pro 2 (ni Three.js)', () => {
    for (const p of ['index', 'résidentiel', 'professionnel', 'contact', 'équipement', 'loi-82-21', 'regularization-article-33']) {
      const page = read(`../src/pages/${p}.astro`);
      expect(page).not.toContain('roof-tool-pro2');
      expect(page).not.toMatch(/from\s+['"]three/);
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
