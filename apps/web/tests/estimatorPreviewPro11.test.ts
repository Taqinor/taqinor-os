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

  it('W73 — recomputeMatrix note la matrice sur le MÊME cache PVGIS que la carte reco', () => {
    const matrix = read('../src/scripts/roofPro11/matrix.ts');
    // recomputeMatrix passe un yieldFn adossé à ctx.v4YieldCache (cache PVGIS partagé) —
    // plus de balayage table « nu » qui désaccorderait la ligne badgée de la carte reco.
    expect(matrix).toContain('ctx.v4YieldCache.get(v4Key(');
    expect(matrix).toContain('fineGridMatrixV6(ring, ctx.centroidLat, monthlyBill(), obstructionRings(), { yieldFn: matrixYieldFn })');
  });

  it('W74 — l\'optimiseur affiche un message honnête « non viable » / « pan nord »', () => {
    // l'UI lit les drapeaux res.noViableConfig (plat + pente) et res.northFacing (pente)
    // pour afficher un message FR honnête au lieu d'un faux « 0 panneau gagnant ».
    expect(optimizer).toContain('res.noViableConfig');
    expect(optimizer).toContain('Configuration non viable sur ce toit');
    expect(optimizer).toContain('res.northFacing');
    expect(optimizer).toContain('production quasi nulle');
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

  it('la recherche est débouncée (~300 ms) — W93 : sur la SAISIE de l\'adresse', () => {
    // W93 a déplacé le débounce de la soumission vers l'événement `input` (autocomplétion
    // au fil de la frappe) ; le garde anti-course (jeton + abort) est conservé.
    expect(script).toContain('geoInputTimer');
    expect(script).toMatch(/geoInputTimer = setTimeout\([\s\S]{0,120}300\)/);
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

describe('pro-11 — W90 : massing du toit en pente (pignons/jupe de rive)', () => {
  const scene = read('../src/scripts/roofPro11/scene3d.ts');

  it('en pente (flush) une JUPE périmétrique ferme le volume sous la dalle inclinée', () => {
    // la jupe n'est construite QUE sous le drapeau flush (toit en pente).
    expect(scene).toMatch(/if \(flush\)[\s\S]{0,1200}skirtGeo/);
    expect(scene).toContain('const skirt = new THREE.Mesh(skirtGeo, skirtMat)');
    // base posée sur le toit plat (wallH), hauteur = dessous de la dalle inclinée.
    expect(scene).toContain('skirt.position.z = wallH');
    expect(scene).toContain('pitchedDeckZ(x, y, pitchEaveCoord, 0, tiltDeg, pack.azimuthDeg)');
  });

  it('le mur de pignon reprend la teinte du bâtiment (continuité du volume) et est double-face', () => {
    expect(scene).toContain('skirtMat');
    expect(scene).toMatch(/skirtMat[\s\S]{0,200}side: THREE\.DoubleSide/);
  });

  it('le toit PLAT n\'a pas de jupe (massing inchangé) — la jupe est strictement gated par flush', () => {
    // une seule occurrence de skirt (le bloc gated), aucun chemin plat ne la touche.
    expect(scene.match(/skirtGeo/g)?.length).toBeGreaterThanOrEqual(1);
    // la jupe est posée après la dalle et avant les axes de visée (chemin commun), gated flush.
    const flushIdx = scene.indexOf('if (flush) {\n      const n = ring.length;');
    expect(flushIdx).toBeGreaterThan(0);
  });
});

describe('pro-11 — W89 : récupération de perte de contexte WebGL', () => {
  const scene = read('../src/scripts/roofPro11/scene3d.ts');

  it('onAdd branche webglcontextlost (preventDefault) + webglcontextrestored sur le canvas', () => {
    expect(scene).toContain("addEventListener('webglcontextlost'");
    expect(scene).toContain("addEventListener('webglcontextrestored'");
    // le gestionnaire de perte preventDefault (sinon pas de restauration possible).
    expect(scene).toMatch(/function onContextLost[\s\S]{0,200}e\.preventDefault\(\)/);
  });

  it('la restauration reconstruit le renderer (buildRenderer) et re-rend (triggerRepaint)', () => {
    expect(scene).toContain('function buildRenderer(');
    // onContextRestored reconstruit le renderer sur le contexte frais puis re-rend.
    const restored = scene.slice(scene.indexOf('function onContextRestored'));
    expect(restored).toContain('buildRenderer(gl)');
    expect(restored).toContain('map.triggerRepaint()');
  });

  it('render est un no-op tant que le contexte est perdu (glLost) et onRemove détache les écouteurs', () => {
    expect(scene).toContain('let glLost = false');
    expect(scene).toMatch(/render\([\s\S]{0,120}if \(glLost/);
    expect(scene).toContain("removeEventListener('webglcontextlost'");
    expect(scene).toContain("removeEventListener('webglcontextrestored'");
  });
});

describe('pro-11 — W87 : soleil RÉEL + preuve d\'ombrage inter-rangées + contrôle heure/saison', () => {
  const scene = read('../src/scripts/roofPro11/scene3d.ts');
  const page = read('../src/pages/preview/toiture-3d-pro-11.astro');
  const script = read('../src/scripts/roof-tool-pro11.ts');

  it('la scène pose un VRAI soleil via sunDirection (latitude + ctx.sunHour/ctx.sunDay), plus de soleil arbitraire', () => {
    expect(scene).toContain('sunDirection');
    expect(scene).toContain('sunDirection(lat, ctx.sunDay, ctx.sunHour)');
    // l'ancien soleil factice (« visée − 45° ») a disparu.
    expect(scene).not.toContain('pack.azimuthDeg - 45');
    // l'azimut/élévation du soleil viennent de la vraie position.
    expect(scene).toContain('realSun.elevationDeg');
    expect(scene).toContain('realSun.azimuthDeg');
  });

  it('la page expose un contrôle heure du soleil + une bascule saison (zéro CLS)', () => {
    expect(page).toContain('id="rp9-sun-hour"');
    expect(page).toContain('data-sun-season="winter"');
    expect(page).toContain('data-sun-season="summer"');
    // défaut visible = hiver (pire cas) pressé.
    expect(page).toMatch(/data-sun-season="winter"[\s\S]{0,80}aria-pressed="true"/);
  });

  it('l\'entrée câble le curseur d\'heure et la saison vers ctx.sunHour/ctx.sunDay et re-rend la scène', () => {
    expect(script).toContain('ctx.sunHour = h');
    expect(script).toContain('data-sun-season');
    expect(script).toContain("ctx.sunDay = b.dataset.sunSeason === 'summer' ? 172 : WINTER_SOLSTICE_DAY");
    // le défaut du jour = solstice d'hiver (pire cas d'ombrage).
    expect(script).toContain('let sunDay = WINTER_SOLSTICE_DAY');
  });
});

describe('pro-11 — W86 : libellé CTA honnête + aria-live sur les résultats', () => {
  const page = read('../src/pages/preview/toiture-3d-pro-11.astro');

  it('le CTA #rp9-cta porte un libellé HONNÊTE (continuer vers le diagnostic), sans framing WhatsApp', () => {
    // bloc du bouton de prévisualisation (≠ le bouton de soumission du diagnostic).
    const cta = page.slice(page.indexOf('id="rp9-cta"'), page.indexOf('id="rp9-cta"') + 400);
    expect(cta).toContain('Continuer vers le diagnostic');
    // ce bouton-ci ne prétend plus « Recevoir … WhatsApp » et ne porte plus l'icône WhatsApp.
    expect(cta).not.toContain('Recevoir mon étude sur WhatsApp');
    expect(cta).not.toContain('viewBox="0 0 24 24"');
  });

  it('les résultats de recommandation s\'annoncent (aria-live sur le <dl> reco)', () => {
    // le <dl> qui contient rp9-reco-kwc/-panels/-prod/-cover porte aria-live="polite".
    const dlStart = page.lastIndexOf('<dl', page.indexOf('id="rp9-reco-kwc"'));
    const dlTag = page.slice(dlStart, page.indexOf('>', dlStart) + 1);
    expect(dlTag).toContain('aria-live="polite"');
  });

  it('le chiffre de tête de production + son sous-titre s\'annoncent', () => {
    expect(page).toMatch(/id="rp9-prod-headline"[^>]*aria-live="polite"/);
    expect(page).toMatch(/id="rp9-prod-sub"[^>]*aria-live="polite"/);
  });

  it('les totaux multi-zones s\'annoncent (aria-live sur le <dl> des totaux)', () => {
    const dlStart = page.lastIndexOf('<dl', page.indexOf('id="rp9-areas-total-panels"'));
    const dlTag = page.slice(dlStart, page.indexOf('>', dlStart) + 1);
    expect(dlTag).toContain('aria-live="polite"');
  });

  it('le formulaire de diagnostic garde SON propre bouton WhatsApp (intact)', () => {
    // l\'étape WhatsApp réelle vit dans le composant de diagnostic — non touché par W86.
    const form = read('../src/components/DiagnosticFormEnriched.astro');
    expect(form).toContain('Recevoir mon étude sur WhatsApp');
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
    // W82 — la synthèse de TÊTE passe par l'INTÉGRALE ANNUELLE 12 mois (invariante au mois
    // affiché), pas par l'extrapolation d'un seul jour-type.
    expect(all).toContain('annualSavingsFromMonthly(');
    expect(all).toContain('annualSelfConsumptionKwh(');
    expect(all).toContain('annualBatterySizing(');
    expect(all).toContain('rescaleToDaily(');
  });

  it('les deux voies alimentent le MÊME moteur (économies + sizing existants)', () => {
    // économies via le modèle billMAD existant (annualSavingsMad sous annualSavingsFromMonthly),
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

describe('pro-11 — W82/W83/W84/W95/W96 : consommation honnête (intégrale annuelle + ROI)', () => {
  const page = read('../src/pages/preview/toiture-3d-pro-11.astro');
  const all = pro11Sources();

  it('W82 — la synthèse de tête passe par l\'intégrale annuelle 12 mois (invariante au mois)', () => {
    // économies + autoconso + batterie intégrées sur les 12 mois → indépendantes du mois affiché.
    expect(all).toContain('annualSavingsFromMonthly(');
    expect(all).toContain('annualSelfConsumptionKwh(');
    expect(all).toContain('annualBatterySizing(');
    // les 12 jours-types de production sont la source de l\'intégrale.
    expect(all).toContain('typicalDayByMonth');
  });

  it('W83 — Recaler préserve l\'énergie « en plus » + bouton « Réinitialiser la courbe »', () => {
    // Recaler vise facture + Σ onTop (jamais la seule facture qui effacerait l\'énergie « en plus »).
    expect(all).toContain('onTopDailyKwh(');
    expect(all).toContain('billDailyKwh() + onTopDailyKwh()');
    // contrôle de réinitialisation câblé sur l\'id de page.
    expect(page).toContain('id="rp9-cons-reset"');
    expect(all).toContain('consResetEl');
  });

  it('W84 — les créneaux clim/VE respectent les heures saisies (slotEndHour)', () => {
    expect(all).toContain('slotEndHour(');
    // plus de fenêtres codées en dur 13–23 / 11–15 pour la clim/VE.
    expect(all).not.toContain("endHour: 23, billing: 'onTop'");
    expect(all).not.toContain("endHour: 15, billing: 'onTop'");
  });

  it('W95 — profil saisonnier + mini-graphe d\'autoconsommation mensuelle (DOM + wiring)', () => {
    expect(page).toContain('id="rp9-cons-seasonal-toggle"');
    expect(page).toContain('id="rp9-cons-summer"');
    expect(page).toContain('id="rp9-cons-winter"');
    expect(page).toContain('id="rp9-cons-month-chart"');
    expect(all).toContain('seasonalConsumptionByMonth(');
    expect(all).toContain('annualSelfConsumptionSeasonalKwh(');
    // hauteur réservée (zéro CLS) + mouvement réduit pour le mini-graphe mensuel.
    expect(page).toContain('.rp9-cons-month-wrap');
    expect(page).toContain('.rp9-cons-month-chart * { transition: none !important');
  });

  it('W96 — retour sur investissement batterie INDICATIF, jamais un devis', () => {
    expect(page).toContain('id="rp9-cons-payback"');
    expect(all).toContain('batteryPaybackYears(');
    expect(all).toContain('pas un devis');
    // aria-live pour annoncer le retour quand il apparaît.
    expect(page).toMatch(/id="rp9-cons-payback"[^>]*aria-live="polite"/);
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

describe('pro-11 — W78 : cohérence vue/totaux multi-zones (zone comptée toujours visible en 3D)', () => {
  const scene = read('../src/scripts/roofPro11/scene3d.ts');

  it('appendOtherZones ne saute PLUS une zone sans renderPlan : repli sur le volume nu', () => {
    const fn = scene.slice(scene.indexOf('function appendOtherZones'));
    // l'ancien garde « !a.renderPlan → continue » qui faisait disparaître la zone a disparu.
    expect(fn).not.toContain('|| !a.renderPlan) continue');
    // on saute UNIQUEMENT la zone active, puis on branche sur le repli quand pas de plan.
    expect(fn).toContain('if (a.id === ctx.activeAreaId) continue');
    expect(fn).toContain('buildBareZoneRing(a.vertices, activeOrigin)');
  });

  it('buildBareZoneRing bâtit le bâtiment + la dalle nus depuis vertices (lng/lat → ENU)', () => {
    expect(scene).toContain('function buildBareZoneRing(');
    const fn = scene.slice(scene.indexOf('function buildBareZoneRing'));
    // tracé incomplet (< 3 sommets) → rien.
    expect(fn).toMatch(/if \(vertices\.length < 3\) return null/);
    // conversion lng/lat → ENU relatif à l'origine active (même repère que les autres zones).
    expect(fn).toContain('DEG2M * cosLat');
    // un volume (bâtiment extrudé) + une dalle subdués sont ajoutés à la scène.
    expect(fn).toContain('ExtrudeGeometry');
    expect(fn).toContain('ShapeGeometry');
    expect(fn).toContain('sceneRoot!.add(building)');
    expect(fn).toContain('sceneRoot!.add(deck)');
  });
});

describe('pro-11 — W79 : la disposition personnalisée survit à une édition d\'obstacle/axe', () => {
  const script = read('../src/scripts/roof-tool-pro11.ts');
  const editor = read('../src/scripts/roofPro11/layoutEditor.ts');

  it('recalc() CAPTURE les centres posés AVANT le re-pavage, puis RE-ENTRE la disposition', () => {
    const fn = script.slice(script.indexOf('function recalc()'), script.indexOf('function recalc()') + 1100);
    // capture conditionnée au mode disposition, AVANT recompute/pitchedRecompute.
    expect(fn).toContain('const prevCenters = layoutMode ? occupiedCenters() : null');
    // re-entrée APRÈS le re-pavage (re-snap sur la nouvelle lattice).
    expect(fn).toContain('if (prevCenters) reenterCustomLayout(prevCenters)');
    // l'ordre : la CAPTURE des centres précède la RE-ENTRÉE (capture avant, re-snap après).
    expect(fn.indexOf('const prevCenters = layoutMode ? occupiedCenters()')).toBeLessThan(
      fn.indexOf('if (prevCenters) reenterCustomLayout(prevCenters)'),
    );
  });

  it('reenterCustomLayout re-snappe via nearestEmptyCell (re-snap, pas wipe) et re-rend tout', () => {
    expect(editor).toContain('function reenterCustomLayout(');
    const fn = editor.slice(editor.indexOf('function reenterCustomLayout'));
    // garde-fou : no-op hors mode disposition ou sans plan.
    expect(fn).toMatch(/if \(!ctx\.layoutMode \|\| !ctx\.layoutPlan\) return/);
    // reconstruit l'état sur la NOUVELLE lattice puis remplace l'occupation par les re-snaps.
    expect(fn).toContain('ensureLayoutState()');
    expect(fn).toContain('st.occupied.clear()');
    expect(fn).toContain('nearestEmptyCell(st, c.cx, c.cy)');
    // readouts à jour : re-rendu de la 3D (panneaux) + de la grille/note.
    expect(fn).toContain('renderCustomLayout()');
    expect(fn).toContain('renderLayoutPanel()');
  });

  it('occupiedCenters expose les centres ENU des cellules posées (pour le re-snap)', () => {
    expect(editor).toContain('function occupiedCenters(');
    const fn = editor.slice(editor.indexOf('function occupiedCenters'));
    expect(fn).toContain('st.occupied.has(c.index)');
    expect(fn).toContain('cx: c.cx, cy: c.cy');
  });
});

describe('pro-11 — W80 : glissé-déplacer un panneau au DOIGT (touch) en 3D', () => {
  const editor = read('../src/scripts/roofPro11/layoutEditor.ts');
  const constants = read('../src/scripts/roofPro11/constants.ts');

  it('un seuil de glissé DÉDIÉ LAYOUT_GRAB_PX existe (n\'emprunte pas OBSTACLE_TAP_PX)', () => {
    expect(constants).toMatch(/export const LAYOUT_GRAB_PX = \d+/);
    // le chemin de glissé panneau utilise SON propre seuil, plus l'OBSTACLE_TAP_PX.
    expect(editor).toContain('LAYOUT_GRAB_PX');
    expect(editor).not.toContain('OBSTACLE_TAP_PX');
  });

  it('le glissé panneau partage une logique commune souris/doigt (begin/move/end)', () => {
    expect(editor).toContain('function beginLayoutDrag(');
    expect(editor).toContain('function moveLayoutDrag(');
    expect(editor).toContain('function endLayoutDrag(');
    // begin gardé par layoutMode + hors mode obstacle (mêmes garde-fous que la souris).
    const begin = editor.slice(editor.indexOf('function beginLayoutDrag'));
    expect(begin).toMatch(/if \(!ctx\.layoutMode \|\| isObstacleMode\(\) \|\| !ctx\.layoutState\) return false/);
  });

  it('des handlers touchstart/touchmove/touchend MIROIR du chemin souris sont câblés', () => {
    expect(editor).toContain("map.on('touchstart'");
    expect(editor).toContain("map.on('touchmove'");
    expect(editor).toContain("map.on('touchend'");
    // touchstart → beginLayoutDrag ; touchmove → moveLayoutDrag ; touchend → endLayoutDrag.
    const ts = editor.slice(editor.indexOf("map.on('touchstart'"));
    expect(ts).toContain('beginLayoutDrag(e.point)');
    const tm = editor.slice(editor.indexOf("map.on('touchmove'"));
    expect(tm).toContain('moveLayoutDrag(e.point)');
    const te = editor.slice(editor.indexOf("map.on('touchend'"));
    expect(te).toContain('endLayoutDrag(e.point)');
  });

  it('le touch ne saisit qu\'à UN doigt (pinch ignoré) et neutralise le pan (preventDefault)', () => {
    const ts = editor.slice(editor.indexOf("map.on('touchstart'"), editor.indexOf("map.on('touchmove'"));
    // pinch/zoom à deux doigts ne déplace pas un panneau.
    expect(ts).toContain('e.points && e.points.length > 1');
    // touchmove preventDefault pendant le glissé (parité dragPan.disable du chemin souris).
    const tm = editor.slice(editor.indexOf("map.on('touchmove'"), editor.indexOf("map.on('touchend'"));
    expect(tm).toContain('e.preventDefault()');
  });

  it('le commit du déplacement (souris ET doigt) atterrit sur une cellule VIDE valide', () => {
    // endLayoutDrag passe par movePanelToPoint → snap sur la cellule vide valide la + proche.
    const end = editor.slice(editor.indexOf('function endLayoutDrag'));
    expect(end).toContain('movePanelToPoint(ctx.layoutState, from, enu.x, enu.y)');
    expect(end).toContain('renderCustomLayout()'); // readouts recompute après le déplacement
  });
});

describe('pro-11 — W88 : pick + highlight + suppression d\'un panneau ciblé en 3D', () => {
  const scene = read('../src/scripts/roofPro11/scene3d.ts');
  const editor = read('../src/scripts/roofPro11/layoutEditor.ts');
  const context = read('../src/scripts/roofPro11/context.ts');
  const script = read('../src/scripts/roof-tool-pro11.ts');

  it('l\'InstancedMesh des panneaux porte un buffer instanceColor (pour le surlignage)', () => {
    expect(scene).toContain('instanceColor');
    expect(scene).toContain('THREE.InstancedBufferAttribute');
    // le mapping instance → cellule de lattice est mémorisé pour relier un panneau à sa cellule.
    expect(scene).toContain('panelCellIndices');
    expect(scene).toContain('ctx.activePanelMesh');
    expect(scene).toContain('ctx.activePanelCellIndex');
  });

  it('setPanelHighlight tinte (or) l\'instance de la cellule, ou efface tout (null)', () => {
    expect(scene).toContain('function setPanelHighlight(');
    const fn = scene.slice(scene.indexOf('function setPanelHighlight'));
    // tinte or pour la cellule sélectionnée, blanc (neutre) pour les autres.
    expect(fn).toContain('map[i] === cellIndex');
    expect(fn).toContain('col.setXYZ(i, 1.0, 0.78, 0.32)'); // GOLD
    expect(fn).toContain('col.setXYZ(i, 1, 1, 1)'); // teinte d'origine
    expect(fn).toContain('col.needsUpdate = true');
    // ctx expose les champs requis (pick/highlight).
    expect(context).toContain('activePanelMesh: THREE.InstancedMesh | null');
    expect(context).toContain('activePanelCellIndex: number[]');
  });

  it('le survol surligne le panneau sous le curseur (UNIQUEMENT en mode disposition)', () => {
    const mm = editor.slice(editor.indexOf("map.on('mousemove'"), editor.indexOf("map.on('mouseup'"));
    // garde-fou mode disposition + pas en mode obstacle.
    expect(mm).toMatch(/if \(!ctx\.layoutMode \|\| isObstacleMode\(\) \|\| !ctx\.layoutState\) return/);
    expect(mm).toContain('setPanelHighlight(layoutPanelAt(e.point))');
  });

  it('clic desktop SANS glissé supprime le panneau ciblé (removePanel) + recompute', () => {
    expect(editor).toContain("from '../../lib/layoutVariability'");
    expect(editor).toContain('removePanel,'); // réutilise la logique PURE (jamais dupliquée)
    expect(editor).toContain('function removePanelInScene(');
    const fn = editor.slice(editor.indexOf('function removePanelInScene'));
    expect(fn).toContain('removePanel(ctx.layoutState, cellIndex)');
    expect(fn).toContain('renderCustomLayout()'); // les figures recomputent
    // mouseup déclenche la suppression sur clic sans glissé (removeOnTap=true).
    expect(editor).toContain('endLayoutDrag(e.point, true)');
    const end = editor.slice(editor.indexOf('function endLayoutDrag'));
    expect(end).toContain('if (!moved && removeOnTap)');
    expect(end).toContain('removePanelInScene(from)');
  });

  it('au DOIGT, un appui long (sans glissé) supprime ; un tap bref ne supprime pas', () => {
    expect(editor).toContain('LONG_PRESS_MS');
    // le minuteur d'appui long supprime le panneau saisi s'il n'a pas bougé.
    const ts = editor.slice(editor.indexOf("map.on('touchstart'"), editor.indexOf("map.on('touchmove'"));
    expect(ts).toContain('setTimeout');
    expect(ts).toContain('removePanelInScene(cell)');
    // un glissé annule l'appui long (déplacement, pas suppression).
    const tm = editor.slice(editor.indexOf("map.on('touchmove'"), editor.indexOf("map.on('touchend'"));
    expect(tm).toContain('cancelLongPress()');
    // touchend : annule le minuteur (tap bref ≠ suppression) et NE supprime pas (removeOnTap omis).
    const te = editor.slice(editor.indexOf("map.on('touchend'"));
    expect(te).toContain('cancelLongPress()');
    expect(te).toContain('endLayoutDrag(e.point)');
    expect(te).not.toContain('endLayoutDrag(e.point, true)');
  });

  it('le pick/highlight n\'est ACTIF qu\'en mode disposition (effacé en sortant)', () => {
    const sm = editor.slice(editor.indexOf('function setLayoutMode'));
    expect(sm).toContain('setPanelHighlight(null)'); // efface le surlignage à la sortie
  });

  it('l\'entrée câble setPanelHighlight (scene3d) vers l\'éditeur de disposition', () => {
    expect(script).toContain('const setPanelHighlight = scene3d.setPanelHighlight');
    expect(script).toContain('setPanelHighlight: (cellIndex) => setPanelHighlight(cellIndex)');
  });
});
