// Garde-fous de la PRÉVISUALISATION privée « estimateur — cerveaux V7 + V8 / W34 + W35 »
// (/preview/toiture-3d-pro-11) : route privée (noindex, hors sitemap), 3D/cerveau
// chargés paresseusement (jamais sur une page publique), et l'OPTIMISEUR CONTRAINT
// VIVANT étendu au TOIT EN PENTE (W35) :
//   - axes LIBRES en pente = pose + marge (+ besoin) ; inclinaison = pente et azimut =
//     face IMPOSÉS (pas d'axe tilt/orientation) ; production PVGIS pose 'building' ;
//   - la pose AFFLEURANTE coplanaire et la 3D pente restent INCHANGÉES (modèle V6) ;
//   - le toit PLAT garde l'optimiseur vivant W34 (V7) intact.
// Tout l'existant (pro-3..pro-10 + le formulaire live) reste strictement intact.
import { describe, expect, it } from 'vitest';
import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const read = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');

// Split modulaire (2026-06-20) : le builder pro-11 est désormais réparti entre
// roof-tool-pro11.ts ET les modules roofPro11/**. Les garde-fous de sécurité
// (« aucun lead posté ») doivent tenir sur TOUTE la surface du builder.
const pro11Sources = (): string => {
  const dir = fileURLToPath(new URL('../src/scripts/roofPro11/', import.meta.url));
  const mods = existsSync(dir)
    ? readdirSync(dir)
        .filter((f) => f.endsWith('.ts'))
        .map((f) => read(`../src/scripts/roofPro11/${f}`))
    : [];
  return [read('../src/scripts/roof-tool-pro11.ts'), ...mods].join('\n');
};

describe('pro-11 — route privée, jamais indexée', () => {
  it('la page /preview/toiture-3d-pro-11 est noindex', () => {
    expect(read('../src/pages/preview/toiture-3d-pro-11.astro')).toContain('noindex={true}');
  });

  it('vit dans le sous-dossier /preview (pas de page top-level)', () => {
    expect(existsSync(fileURLToPath(new URL('../src/pages/preview/toiture-3d-pro-11.astro', import.meta.url)))).toBe(true);
    expect(existsSync(fileURLToPath(new URL('../src/pages/toiture-3d-pro-11.astro', import.meta.url)))).toBe(false);
  });
});

describe('pro-11 — 3D + cerveau chargés paresseusement, hors page publique', () => {
  it('la page importe SON script pro-11 via import() dynamique, jamais en statique', () => {
    const src = read('../src/pages/preview/toiture-3d-pro-11.astro');
    expect(src).toContain("import('../../scripts/roof-tool-pro11.ts')");
    expect(src).not.toContain("scripts/roof-tool-pro10.ts"); // n'emprunte PAS le script pro-10
    expect(src).not.toContain("from 'three'");
    expect(src).not.toContain("from 'maplibre-gl'");
  });

  it('le script lourd reste hors de toute page publique', () => {
    for (const p of ['index', 'résidentiel', 'professionnel', 'contact', 'équipement', 'à-propos']) {
      const src = read(`../src/pages/${p}.astro`);
      expect(src, `${p}: pas de roof-tool-pro11`).not.toContain('roof-tool-pro11');
      expect(src, `${p}: pas de cerveau estimateur`).not.toContain('estimatorBrain');
    }
  });

  it('le script ne poste aucun lead — il ne fait que pré-remplir les champs', () => {
    // Garde-fou de sécurité élargi à TOUTE la surface du builder (split modulaire).
    const all = pro11Sources();
    expect(all).not.toContain('/api/preview-lead');
    expect(all).not.toContain('/api/simulate');
    expect(all).toContain('prefillLead(');
  });
});

describe('pro-11 — W35 : optimiseur contraint VIVANT en pente (cerveau V8)', () => {
  const script = read('../src/scripts/roof-tool-pro11.ts');
  // Split modulaire : le moteur d'optimisation vit dans roofPro11/optimizer.ts.
  const optimizer = read('../src/scripts/roofPro11/optimizer.ts');

  it('le script branche le cerveau V8 (solveLivePitched) et re-résout en direct', () => {
    expect(optimizer).toContain("from '../../lib/estimatorBrainV8'");
    expect(optimizer).toContain('solveLivePitched(');
    expect(optimizer).toContain('function liveResolvePitched(');
  });

  it('production pente = PVGIS au (pente, face), pose « building » (cache partagé)', () => {
    expect(optimizer).toContain('ctx.pitchedYieldCache.get(pitchedKey(');
    expect(optimizer).toContain("mountingplace: 'building'");
    expect(optimizer).toContain('pitchedPlaneLeg(');
    // après l'arrivée PVGIS, l'optimiseur pente se re-résout
    expect(optimizer).toMatch(/refinePitchedPvgis[\s\S]{0,600}liveResolvePitched\(\)/);
  });

  it('axes LIBRES en pente = pose + marge (+ besoin) ; verrous cumulatifs + Réinitialiser', () => {
    expect(optimizer).toContain('pitchedLocks');
    expect(optimizer).toContain('function resetPitchedLocks(');
    // le bouton Réinitialiser route en pente — câblage DOM resté dans l'entrée
    expect(script).toContain("if (roofType === 'pitched') resetPitchedLocks();");
  });

  it('chaque groupe pente montre sa valeur « Recommandé » (pose/marge)', () => {
    expect(optimizer).toContain('function updatePitchedBadges(');
    expect(optimizer).toContain('res.recommended');
  });

  it('un comparatif pente (pose × marge) est rendu, l\'optimum badgé', () => {
    expect(optimizer).toContain('function paintPitchedComparison(');
    expect(optimizer).toContain('✓ Recommandé');
    // la matrice PLATE ne repeint jamais le tableau en mode pente — la garde vit
    // désormais dans roofPro11/matrix.ts (split modulaire), sous forme ctx.*.
    const matrix = read('../src/scripts/roofPro11/matrix.ts');
    expect(matrix).toContain("if (ctx.roofType !== 'flat' || !ctx.rec || !ctx.matrixResult) return;");
  });
});

describe('pro-11 — la pose AFFLEURANTE et la 3D pente restent INCHANGÉES (modèle V6)', () => {
  const script = read('../src/scripts/roof-tool-pro11.ts');
  it('rendu pente : plan incliné + pose coplanaire (géométrie V6), flush=true', () => {
    // Split modulaire : la géométrie V6 (plan incliné + pose coplanaire affleurante) vit
    // dans roofPro11/scene3d.ts ; l'appel renderScene(…, true) en pente (renderPitchedWinner)
    // vit dans roofPro11/optimizer.ts.
    const scene = read('../src/scripts/roofPro11/scene3d.ts');
    expect(scene).toContain('pitchedDeckZ(');
    expect(scene).toContain('flushPanelCenterAt(');
    expect(scene).toContain('PITCHED_FLUSH_STANDOFF_M');
    // renderScene rendu avec flush=true en pente (dernier argument)
    const optimizer = read('../src/scripts/roofPro11/optimizer.ts');
    expect(optimizer).toContain("'south', w.placedCount, true)");
  });
  it('le type de toit est toujours choisi AVANT le tracé (preset 45° conservé)', () => {
    const page = read('../src/pages/preview/toiture-3d-pro-11.astro');
    expect(page).toContain('id="rp9-rooftype-first"');
    for (const p of ['data-pitch="15"', 'data-pitch="22"', 'data-pitch="30"', 'data-pitch="45"']) {
      expect(page, p).toContain(p);
    }
  });
  it('la page montre la pose + la marge dans les DEUX modes (axes libres en pente)', () => {
    const page = read('../src/pages/preview/toiture-3d-pro-11.astro');
    // les contrôles propres au plat sont dans #rp9-flat-only (masqué en pente)
    expect(page).toContain('id="rp9-flat-only"');
    // pose (data-orient) + marge (data-margin) restent hors de #rp9-flat-only
    const flatOnly = page.slice(page.indexOf('id="rp9-flat-only"'), page.indexOf('/rp9-flat-only'));
    expect(flatOnly).not.toContain('data-orient="portrait"');
    expect(flatOnly).not.toContain('data-margin="keep"');
    expect(page).toContain('data-orient="portrait"');
    expect(page).toContain('data-margin="keep"');
  });
});

describe('pro-11 — W47 : « Alignée toit » présente/forcée en pente, orientations impossibles retirées', () => {
  const page = read('../src/pages/preview/toiture-3d-pro-11.astro');

  it('le bloc pente PRÉSENTE « Alignée toit » comme orientation par défaut et FORCÉE (lecture seule)', () => {
    const pitched = page.slice(page.indexOf('id="rp9-pitched-controls"'), page.indexOf('id="rp9-obs-edit"'));
    expect(pitched).toContain('data-pitched-orient="aligned"');
    expect(pitched).toContain('Alignée toit');
    // forcée / lecture seule : pressée + désactivée (l\'utilisateur ne peut pas la changer)
    expect(pitched).toMatch(/data-pitched-orient="aligned"[\s\S]{0,200}aria-pressed="true"/);
    expect(pitched).toMatch(/data-pitched-orient="aligned"[\s\S]{0,200}disabled/);
  });

  it('les orientations PHYSIQUEMENT impossibles (plein-sud tourné, Est-Ouest) restent dans #rp9-flat-only (masqué en pente)', () => {
    // famille (plein sud / Est-Ouest) + azimut sont confinés à #rp9-flat-only, que setRoofType
    // masque en pente — donc jamais offerts au toit en pente.
    const flatOnly = page.slice(page.indexOf('id="rp9-flat-only"'), page.indexOf('/rp9-flat-only'));
    expect(flatOnly).toContain('data-family="eastwest"');
    expect(flatOnly).toContain('data-family="south"');
    expect(flatOnly).toContain('id="rp9-azimuth-group"');
    // le bloc pente n\'offre AUCUNE de ces orientations impossibles
    const pitched = page.slice(page.indexOf('id="rp9-pitched-controls"'), page.indexOf('id="rp9-obs-edit"'));
    expect(pitched).not.toContain('data-family=');
    expect(pitched).not.toContain('data-azimuth=');
  });

  it('setRoofType masque #rp9-flat-only en pente (orientations plates non offertes)', () => {
    const script = read('../src/scripts/roof-tool-pro11.ts');
    expect(script).toContain("flatOnlyEl.hidden = t !== 'flat'");
  });
});

describe('pro-11 — le toit PLAT garde l\'optimiseur vivant W34 (V7) intact', () => {
  // Split modulaire : le moteur d'optimisation vivante vit dans roofPro11/optimizer.ts.
  const optimizer = read('../src/scripts/roofPro11/optimizer.ts');
  it('V7 solveLive + liveResolveFlat toujours présents (toit plat inchangé)', () => {
    expect(optimizer).toContain("from '../../lib/estimatorBrainV7'");
    expect(optimizer).toContain('solveLive(');
    expect(optimizer).toContain('function liveResolveFlat(');
    expect(optimizer).toContain('function resetFlatLocks(');
  });
});

describe('pro-11 — W75 : recherche d\'adresse anti-course (jeton + abort + débounce)', () => {
  // Split modulaire : le géocodage W75 vit désormais dans roofPro11/mapDraw.ts.
  const script = read('../src/scripts/roofPro11/mapDraw.ts');

  it('geocode capture un jeton de requête et ignore les réponses périmées', () => {
    expect(script).toContain('let geoToken = 0');
    expect(script).toContain('const myToken = ++geoToken');
    expect(script).toContain('if (myToken !== geoToken) return');
  });

  it('le fetch porte un AbortController (la requête précédente est annulée)', () => {
    expect(script).toContain('new AbortController()');
    expect(script).toContain('geoAbort?.abort()');
    expect(script).toContain('fetch(url, { signal: ctrl.signal })');
  });

  it('la soumission de recherche est débouncée (~300 ms)', () => {
    expect(script).toContain('geoSubmitTimer');
    expect(script).toMatch(/geoSubmitTimer = setTimeout\([\s\S]{0,120}300\)/);
  });
});

describe('pro-11 — W70 : libération des ressources GPU (re-tracé + démontage)', () => {
  // Split modulaire : la scène 3D (couche custom + photo de toit) vit dans roofPro11/scene3d.ts.
  const script = read('../src/scripts/roofPro11/scene3d.ts');

  it('la couche custom expose onRemove qui libère renderer + textures + scène', () => {
    expect(script).toContain('onRemove(');
    expect(script).toContain('renderer?.dispose()');
    expect(script).toContain('panelTex.dispose()');
  });

  it('applyRoofPhoto libère l\'ancienne texture de toit avant de la remplacer (orpheline seule)', () => {
    // garde anti double-libération : ne touche pas la texture encore montée sur le deck.
    expect(script).toContain('roofTex !== deckMaterial?.map');
    expect(script).toContain('roofTex.dispose()');
  });
});

describe('pro-11 — W71 : matériaux + géométries statiques hoistés hors du chemin de rendu', () => {
  const script = read('../src/scripts/roofPro11/scene3d.ts');

  it('le système panneau a un cache de matériaux (active + dim) réutilisé par rendu', () => {
    // les matériaux ne sont plus ré-alloués DANS buildZoneMeshes : une fabrique + un cache.
    expect(script).toContain('panelMatsActive');
    expect(script).toContain('panelMatsDim');
    expect(script).toContain('const buildPanelMatSet');
    expect(script).toContain('panelMatSet(dim)');
    // le verre MeshPhysicalMaterial (recompilation de shader) n'est construit que dans la fabrique
    expect(script.match(/new THREE\.MeshPhysicalMaterial/g)?.length).toBe(1);
  });

  it('les géométries STATIQUES (boîtier/montant avant/lest) sont cachées une fois', () => {
    expect(script).toContain('jboxGeoOf()');
    expect(script).toContain('frontGeoOf(frontStrut)');
    expect(script).toContain('ballastGeoOf()');
  });

  it('disposeScene ne libère JAMAIS le cache partagé (seul disposeSharedCache à onRemove)', () => {
    // garde anti-corruption : disposeObject saute les ressources partagées.
    expect(script).toContain('sharedResources');
    expect(script).toContain('!sharedResources.has(holder.geometry)');
    expect(script).toContain('!sharedResources.has(m)');
    // le cache n'est libéré qu'au démontage de la couche (onRemove), pas par rendu.
    expect(script).toContain('disposeSharedCache()');
    expect(script).toMatch(/onRemove\([\s\S]{0,200}disposeSharedCache\(\)/);
  });
});

describe('pro-11 — l\'existant est strictement préservé', () => {
  it('les baselines pro-3..pro-10 gardent leur page et leur script dédiés', () => {
    for (const n of [3, 4, 5, 6, 7, 8, 9, 10]) {
      expect(read(`../src/pages/preview/toiture-3d-pro-${n}.astro`)).toContain(`import('../../scripts/roof-tool-pro${n}.ts')`);
      expect(existsSync(fileURLToPath(new URL(`../src/scripts/roof-tool-pro${n}.ts`, import.meta.url)))).toBe(true);
    }
  });

  it('pro-10 reste en V7 (toit plat) et N\'utilise PAS le cerveau V8', () => {
    const pro10 = read('../src/scripts/roof-tool-pro10.ts');
    expect(pro10).toContain("from '../lib/estimatorBrainV7'");
    expect(pro10).not.toContain("from '../lib/estimatorBrainV8'");
    expect(pro10).not.toContain('solveLivePitched(');
  });

  it('le moteur V8 compose sur V2 + V3 sans les ré-implémenter (pas d\'édition)', () => {
    const v8 = read('../src/lib/estimatorBrainV8.ts');
    expect(v8).toContain("from './estimatorBrainV2'");
    expect(v8).toContain("from './estimatorBrainV3'");
    expect(v8).toContain('export function solveLivePitched');
    expect(v8).toContain('packFlushPlane('); // pavage affleurant V3 réutilisé
  });

  it('le proxy /api/roof-yield garde « building » par défaut ; « free » seulement si demandé', () => {
    const route = read('../src/pages/api/roof-yield.ts');
    expect(route).toContain("body.mountingplace === 'free' ? 'free' : 'building'");
  });
});

describe('pro-11 — W68 : mode VARIABILITÉ de consommation (« Affiner ma consommation »)', () => {
  const page = read('../src/pages/preview/toiture-3d-pro-11.astro');

  it('la page expose un contrôle « Affiner ma consommation » + le panneau d\'affinage', () => {
    expect(page).toContain('Affiner ma consommation');
    expect(page).toContain('id="rp9-cons-window"');
    expect(page).toContain('id="rp9-cons-toggle"');
    expect(page).toContain('id="rp9-cons-panel"');
  });

  it('édition à la main : graphe de barres glissables + saisie numérique des 24 h', () => {
    expect(page).toContain('id="rp9-cons-graph"'); // barres glissables
    expect(page).toContain('id="rp9-cons-inputs"'); // saisie numérique (mobile / mouvement réduit)
    expect(page).toContain('Recaler sur ma facture');
    expect(page).toContain('id="rp9-cons-recal"');
  });

  it('calculateur d\'appareils : sélecteur, saisie clim (BTU) et voiture (kW/km)', () => {
    expect(page).toContain('id="rp9-appl-kind"');
    expect(page).toContain('id="rp9-appl-add"');
    expect(page).toContain('id="rp9-ac-btu"'); // climatisation par BTU
    expect(page).toContain('id="rp9-ac-eer"'); // ÷ EER
    expect(page).toContain('id="rp9-ev-kw"'); // chargeur kW
    expect(page).toContain('id="rp9-ev-km"'); // ou km/jour
  });

  it('synthèse : total conso, autoconsommation, économies plafonnées, batterie', () => {
    expect(page).toContain('id="rp9-cons-total"');
    expect(page).toContain('id="rp9-cons-self"');
    expect(page).toContain('id="rp9-cons-savings"');
    expect(page).toContain('id="rp9-cons-batt"');
  });

  // Split modulaire : la logique de consommation vit dans roofPro11/consumption.ts.
  // On vérifie l'intégralité de la surface du builder (jamais dupliquée).
  const all = pro11Sources();

  it('le script branche la logique PURE applianceConsumption (jamais dupliquée)', () => {
    expect(all).toContain("lib/applianceConsumption'");
    expect(all).toContain('composeConsumption(');
    expect(all).toContain('savingsFromHourly(');
    expect(all).toContain('batterySizing(');
    expect(all).toContain('rescaleToDaily(');
  });

  it('les deux voies alimentent le MÊME moteur (économies + sizing existants)', () => {
    // économies via le modèle billMAD existant (annualSavingsMad sous savingsFromHourly),
    // sizing via le besoin existant (neededPanelsForTarget → renderActive).
    expect(all).toContain('applyConsumptionToSizing');
    expect(all).toContain('neededPanelsForTarget(');
    expect(all).toContain('renderActive()');
  });

  it('« sur ma facture » vs « déjà compris » + recalage sont câblés', () => {
    expect(all).toContain('data-appl-toggle'); // bascule onTop / inBill
    expect(all).toContain("billing === 'onTop'");
    expect(all).toContain('consHandEdited'); // override manuel suivi
  });

  it('un fichier de sources d\'appareils existe (typiques éditables, jamais inventés)', () => {
    expect(existsSync(fileURLToPath(new URL('../APPLIANCES_NOTES.md', import.meta.url)))).toBe(true);
  });
});

describe('pro-11 — W69 : mode VARIABILITÉ de disposition (« Personnaliser la disposition »)', () => {
  const page = read('../src/pages/preview/toiture-3d-pro-11.astro');

  it('la page expose un contrôle « Personnaliser la disposition » + le panneau', () => {
    expect(page).toContain('Personnaliser la disposition');
    expect(page).toContain('id="rp9-layout-window"');
    expect(page).toContain('id="rp9-layout-toggle"');
    expect(page).toContain('id="rp9-layout-panel"');
  });

  it('boutons +/− (touch + mouvement réduit), réinitialiser, et plan tactile', () => {
    expect(page).toContain('id="rp9-layout-plus"');
    expect(page).toContain('id="rp9-layout-minus"');
    expect(page).toContain('Réinitialiser la disposition optimale');
    expect(page).toContain('id="rp9-layout-reset"');
    expect(page).toContain('id="rp9-layout-grid"'); // plan des emplacements (tap-sélection → tap-cible)
  });

  it('synthèse de disposition : posés / kWc / libres / couverture', () => {
    expect(page).toContain('id="rp9-layout-count"');
    expect(page).toContain('id="rp9-layout-kwc"');
    expect(page).toContain('id="rp9-layout-free"');
    expect(page).toContain('id="rp9-layout-cover"');
  });

  it('le script branche la logique PURE layoutVariability (jamais dupliquée)', () => {
    // Split modulaire : W69 vit dans roofPro11/layoutEditor.ts — on scanne tout le builder.
    const builder = pro11Sources();
    expect(builder).toContain("from '../../lib/layoutVariability'");
    expect(builder).toContain('createLayoutState(');
    expect(builder).toContain('movePanelToPoint('); // glissé-snap
    expect(builder).toContain('movePanelToCell('); // tap-cible
    expect(builder).toContain('resetToOptimal('); // réinitialiser
  });

  it('recompute par COMPTAGE via le chemin de production existant (rendement/panneau inchangé)', () => {
    // déplacer dans le même plan → même rendement ; seul le nombre change la production.
    const builder = pro11Sources();
    expect(builder).toContain('renderCustomLayout');
    expect(builder).toContain('updateProductionWindow('); // chemin PVGIS-par-comptage existant
    // renderScene rend l'occupation personnalisée (cellules potentiellement non contiguës)
    expect(builder).toContain('occupiedSet');
  });

  it('glissé sur la 3D : déprojection → snap (raycast sur le plan du toit)', () => {
    const builder = pro11Sources();
    expect(builder).toContain('screenToENU(');
    expect(builder).toContain('map.unproject('); // raycast → plan du toit
    expect(builder).toContain('nearestEmptyCell(');
  });

  it('le plan des emplacements signale valide (vert) / invalide (rouge) par CSS', () => {
    expect(page).toContain("data-occupied='false']:hover"); // cible valide = vert
    expect(page).toContain('rgb(74 222 128'); // vert (valide)
    expect(page).toContain('rgb(248 113 113'); // rouge (invalide/occupée)
  });
});
