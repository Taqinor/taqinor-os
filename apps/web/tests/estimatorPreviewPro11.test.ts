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
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const read = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');

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
    const script = read('../src/scripts/roof-tool-pro11.ts');
    expect(script).not.toContain('/api/preview-lead');
    expect(script).not.toContain('/api/simulate');
    expect(script).toContain('prefillLead(');
  });
});

describe('pro-11 — W35 : optimiseur contraint VIVANT en pente (cerveau V8)', () => {
  const script = read('../src/scripts/roof-tool-pro11.ts');

  it('le script branche le cerveau V8 (solveLivePitched) et re-résout en direct', () => {
    expect(script).toContain("from '../lib/estimatorBrainV8'");
    expect(script).toContain('solveLivePitched(');
    expect(script).toContain('function liveResolvePitched(');
  });

  it('production pente = PVGIS au (pente, face), pose « building » (cache partagé)', () => {
    expect(script).toContain('pitchedYieldCache.get(pitchedKey(');
    expect(script).toContain("mountingplace: 'building'");
    expect(script).toContain('pitchedPlaneLeg(');
    // après l'arrivée PVGIS, l'optimiseur pente se re-résout
    expect(script).toMatch(/refinePitchedPvgis[\s\S]{0,600}liveResolvePitched\(\)/);
  });

  it('axes LIBRES en pente = pose + marge (+ besoin) ; verrous cumulatifs + Réinitialiser', () => {
    expect(script).toContain('pitchedLocks');
    expect(script).toContain('function resetPitchedLocks(');
    expect(script).toContain("if (roofType === 'pitched') resetPitchedLocks();"); // le bouton Réinitialiser route en pente
  });

  it('chaque groupe pente montre sa valeur « Recommandé » (pose/marge)', () => {
    expect(script).toContain('function updatePitchedBadges(');
    expect(script).toContain('res.recommended');
  });

  it('un comparatif pente (pose × marge) est rendu, l\'optimum badgé', () => {
    expect(script).toContain('function paintPitchedComparison(');
    expect(script).toContain('✓ Recommandé');
    // la matrice PLATE ne repeint jamais le tableau en mode pente
    expect(script).toContain("if (roofType !== 'flat' || !rec || !matrixResult) return;");
  });
});

describe('pro-11 — la pose AFFLEURANTE et la 3D pente restent INCHANGÉES (modèle V6)', () => {
  const script = read('../src/scripts/roof-tool-pro11.ts');
  it('rendu pente : plan incliné + pose coplanaire (géométrie V6), flush=true', () => {
    expect(script).toContain('pitchedDeckZ(');
    expect(script).toContain('flushPanelCenterAt(');
    expect(script).toContain('PITCHED_FLUSH_STANDOFF_M');
    // renderScene rendu avec flush=true en pente (dernier argument)
    expect(script).toContain("'south', w.placedCount, true)");
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
  const script = read('../src/scripts/roof-tool-pro11.ts');
  it('V7 solveLive + liveResolveFlat toujours présents (toit plat inchangé)', () => {
    expect(script).toContain("from '../lib/estimatorBrainV7'");
    expect(script).toContain('solveLive(');
    expect(script).toContain('function liveResolveFlat(');
    expect(script).toContain('function resetFlatLocks(');
  });
});

describe('pro-11 — W75 : recherche d\'adresse anti-course (jeton + abort + débounce)', () => {
  const script = read('../src/scripts/roof-tool-pro11.ts');

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
  const script = read('../src/scripts/roof-tool-pro11.ts');

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
  const script = read('../src/scripts/roof-tool-pro11.ts');

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

  it('le script branche la logique PURE applianceConsumption (jamais dupliquée)', () => {
    expect(script).toContain("from '../lib/applianceConsumption'");
    expect(script).toContain('composeConsumption(');
    expect(script).toContain('savingsFromHourly(');
    expect(script).toContain('batterySizing(');
    expect(script).toContain('rescaleToDaily(');
  });

  it('les deux voies alimentent le MÊME moteur (économies + sizing existants)', () => {
    // économies via le modèle billMAD existant (annualSavingsMad sous savingsFromHourly),
    // sizing via le besoin existant (neededPanelsForTarget → renderActive).
    expect(script).toContain('applyConsumptionToSizing');
    expect(script).toContain('neededPanelsForTarget(');
    expect(script).toContain('renderActive()');
  });

  it('« sur ma facture » vs « déjà compris » + recalage sont câblés', () => {
    expect(script).toContain('data-appl-toggle'); // bascule onTop / inBill
    expect(script).toContain("billing === 'onTop'");
    expect(script).toContain('consHandEdited'); // override manuel suivi
  });

  it('un fichier de sources d\'appareils existe (typiques éditables, jamais inventés)', () => {
    expect(existsSync(fileURLToPath(new URL('../APPLIANCES_NOTES.md', import.meta.url)))).toBe(true);
  });
});

describe('pro-11 — W69 : mode VARIABILITÉ de disposition (« Personnaliser la disposition »)', () => {
  const page = read('../src/pages/preview/toiture-3d-pro-11.astro');
  const script = read('../src/scripts/roof-tool-pro11.ts');

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
    expect(script).toContain("from '../lib/layoutVariability'");
    expect(script).toContain('createLayoutState(');
    expect(script).toContain('movePanelToPoint('); // glissé-snap
    expect(script).toContain('movePanelToCell('); // tap-cible
    expect(script).toContain('resetToOptimal('); // réinitialiser
  });

  it('recompute par COMPTAGE via le chemin de production existant (rendement/panneau inchangé)', () => {
    // déplacer dans le même plan → même rendement ; seul le nombre change la production.
    expect(script).toContain('renderCustomLayout');
    expect(script).toContain('updateProductionWindow('); // chemin PVGIS-par-comptage existant
    // renderScene rend l'occupation personnalisée (cellules potentiellement non contiguës)
    expect(script).toContain('occupiedSet');
  });

  it('glissé sur la 3D : déprojection → snap (raycast sur le plan du toit)', () => {
    expect(script).toContain('screenToENU(');
    expect(script).toContain('map.unproject('); // raycast → plan du toit
    expect(script).toContain('nearestEmptyCell(');
  });

  it('le plan des emplacements signale valide (vert) / invalide (rouge) par CSS', () => {
    expect(page).toContain("data-occupied='false']:hover"); // cible valide = vert
    expect(page).toContain('rgb(74 222 128'); // vert (valide)
    expect(page).toContain('rgb(248 113 113'); // rouge (invalide/occupée)
  });
});
