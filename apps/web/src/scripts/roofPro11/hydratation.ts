/**
 * ACAL26 — UNE SEULE FONCTION D'HYDRATATION pour les DEUX boots de l'atelier.
 *
 * Constat C-ACAL-045 (live ATL-01/04/05/06) : le document rouvert portait des surfaces de
 * pose, des objets d'environnement, une matrice d'ombrage enregistrée, une consommation
 * affinée et une couche électrique ; les lecteurs existaient (`lireSurfacesPose`,
 * `deserializeEnvironment`, `deserializeShading`, `deserializeConsumptionFromLayout`,
 * `lireCoucheElectrique`) mais AUCUN boot ne posait leur résultat dans le ctx — « Enregistrer »
 * sans geste les effaçait donc toutes.
 *
 * Ce module ne LIT rien (la lecture reste dans `prefill.ts` : `hydrateFromDevis`,
 * `hydrateFromLead`, `lireCouchesDocument`) : il APPLIQUE. `applyHydration` (boot lead) et
 * `applyDevisHydration` (boot devis / calepinage) de `roof-tool-pro11.ts` délèguent ici ;
 * `builderApi.appliquerSection(cle, valeur)` (onglets du Rail) applique UNE clé par la même
 * fonction.
 *
 * Il porte aussi `composerMetaSerialisation`, la composition des métadonnées de sérialisation
 * extraite du wrapper `onApiReady.serializeLayout` : ses DEUX branches (devis / lead) passent
 * désormais la couche électrique, et un test peut appeler le VRAI sérialiseur câblé.
 */
import { annualShadeFactor, type ShadeObstruction } from '../../lib/shadingEngine';
import { fallbackPerKwc } from '../../lib/productionEngine';
import { type PerimeterSetbacks } from '../../lib/roofPro2';
import { type Ctx } from './context';
import {
  deserializeExclusionZonesFromLayout,
  deserializeHorizonProfileFromLayout,
  deserializeMeasurements,
  deserializeSceneFromLayout,
  deserializeSetbacksFromLayout,
  lireCouchesDocument,
  serializeLayout,
  type ConsumptionHydration,
  type CouchesDocument,
  type LayoutScenario,
  type SerializeMeta,
  type SerializedLayout,
} from './prefill';
import { type CoucheElectrique } from './electrique3d';
import { type AffectationModules } from './moduleSelect';
import { lireBatiments } from './batiment'; // ACAL31

/** Ce que l'hydratation peut poser dans le ctx — chaque clé ABSENTE est laissée intacte
 *  (c'est ce qui permet d'appliquer UNE section sans toucher aux autres). */
export type HydratationAtelier = Partial<CouchesDocument & ConsumptionHydration>;

/** Copie profonde JSON-sûre (le document est un JSON pur) : aucun alias entre le payload
 *  relu et l'état vivant de l'atelier. */
function copie<T>(v: T): T {
  return v == null ? v : (JSON.parse(JSON.stringify(v)) as T);
}

/**
 * ACAL26 — pose dans le ctx les couches relues d'un document. Aucun accès DOM : le
 * rafraîchissement des écrans (liste des surfaces, environnement, couche électrique) reste
 * à l'appelant. Une clé absente de `h` n'est jamais touchée.
 *
 *  - `surfacesPose` → `ctx.surfacesPose` (copie) ;
 *  - `environment` → `ctx.environment`, MUTÉ EN PLACE (le tableau est une référence stable
 *    partagée avec `obstaclesUi`/`shadingUi`) ;
 *  - `shading12x24` → `ctx.shadeFactors` + `ctx.ombrageEnregistre` : la matrice enregistrée
 *    prime sur le recalcul tant qu'aucune source d'ombrage ne change (`shadingUi.ts`) ;
 *  - `shadeObstructions` (ACAL27) → `ctx.shadeObstructions` (muté en place) + les entrées
 *    non recalculables dans `ctx.shadeObstructionsNonLues` ;
 *  - les six champs `cons*` + `consSource` → la consommation du SITE (un facteur saisonnier
 *    `null` = non renseigné : le défaut de l'atelier est gardé) ;
 *  - `electrical` → `ctx.electrical` (null = aucune couche) ;
 *  - `choixConception` (ACAL29) → `ctx.sel` / `ctx.pinned` (axes épinglés), AVANT le pavage.
 */
export function appliquerHydratationAuCtx(ctx: Ctx, h: HydratationAtelier): void {
  if (h.surfacesPose !== undefined) ctx.surfacesPose = copie(h.surfacesPose ?? []);
  if (h.environment !== undefined) {
    const env = ctx.environment ?? (ctx.environment = []);
    env.length = 0;
    for (const o of h.environment ?? []) env.push(copie(o));
  }
  if (h.shading12x24 !== undefined) {
    if (h.shading12x24) {
      const matrice = copie(h.shading12x24);
      ctx.ombrageEnregistre = { matrice: copie(matrice), signature: null };
      ctx.shadeFactors = matrice;
      ctx.shadeAnnualFactor = annualShadeFactor(ctx.prodPerKwc ?? fallbackPerKwc(), matrice);
    } else {
      ctx.ombrageEnregistre = null;
    }
  }
  // ACAL27 — les ombres tracées relues (tableau partagé, muté en place) et celles que
  // l'atelier ne sait pas recalculer (transmises telles quelles).
  if (h.shadeObstructions !== undefined) {
    const relues = (h.shadeObstructions ?? []).map((o) => copie(o));
    const liste = ctx.shadeObstructions as ShadeObstruction[] | undefined;
    if (liste) {
      liste.length = 0;
      liste.push(...relues);
    } else {
      (ctx as { shadeObstructions?: ShadeObstruction[] }).shadeObstructions = relues;
    }
  }
  if (h.shadeObstructionsNonLues !== undefined) ctx.shadeObstructionsNonLues = copie(h.shadeObstructionsNonLues ?? []);
  // ACAL29 — les choix épinglés repartent dans `sel`/`pinned` AVANT le pavage (l'appelant
  // applique l'hydratation avant `close()`) : l'optimiseur repave la même grille.
  if (h.choixConception !== undefined) {
    const choix = h.choixConception;
    if (choix) {
      ctx.sel = { ...ctx.sel, ...choix.sel };
      const pins = ctx.pinned as Set<(typeof choix.epingles)[number]> | undefined;
      if (pins) {
        pins.clear();
        for (const a of choix.epingles) pins.add(a);
      }
      ctx.useRecommended = false;
      ctx.choixConceptionRelu = copie(choix.brut);
    } else {
      ctx.choixConceptionRelu = null;
    }
  }
  // ACAL31 — le document relu : il porte aussi les couches que le boot devis lisait EN LIGNE
  // (mesures, zones d'exclusion, retraits, horizon, scène, bâtiments, fond) — désormais lues
  // ici, pour les DEUX boots, par les mêmes lecteurs.
  if (h.documentRelu !== undefined) {
    const doc = h.documentRelu;
    ctx.documentRelu = doc ? copie(doc) : null;
    if (doc) {
      ctx.measurements = deserializeMeasurements(doc);
      const zx = ctx.exclusionZones as unknown[] | undefined;
      const relues = deserializeExclusionZonesFromLayout(doc);
      if (zx) {
        zx.length = 0;
        zx.push(...relues);
      } else {
        ctx.exclusionZones = relues;
      }
      const retraits = deserializeSetbacksFromLayout(doc);
      if (retraits && ctx.setbacks) Object.assign(ctx.setbacks, retraits);
      ctx.horizonProfile = deserializeHorizonProfileFromLayout(doc) as unknown as Ctx['horizonProfile'];
      const scene = deserializeSceneFromLayout(doc);
      if (scene) {
        ctx.sunDay = scene.sunDay;
        ctx.sunHour = scene.sunHour;
      }
      ctx.batiments = lireBatiments(doc);
      if (doc.underlay != null) ctx.underlay = copie(doc.underlay);
    }
  }
  if (h.modulesDuDocument !== undefined) ctx.modulesDuDocument = copie(h.modulesDuDocument ?? []); // ACAL30
  if (h.consCurve !== undefined) ctx.consCurve = (h.consCurve ?? []).slice();
  if (h.consHandEdited !== undefined) ctx.consHandEdited = Boolean(h.consHandEdited);
  if (h.consAppliances !== undefined) ctx.consAppliances = copie(h.consAppliances ?? []);
  if (h.consSeasonal !== undefined) ctx.consSeasonal = Boolean(h.consSeasonal);
  if (typeof h.consSummerFactor === 'number') ctx.consSummerFactor = h.consSummerFactor;
  if (typeof h.consWinterFactor === 'number') ctx.consWinterFactor = h.consWinterFactor;
  if (h.consSource !== undefined) ctx.consSource = h.consSource ? { ...h.consSource } : null;
  if (h.electrical !== undefined) ctx.electrical = h.electrical ? copie(h.electrical) : null;
}

/** ACAL26 — les sections qu'un onglet du Rail peut appliquer une à une. */
export type CleSectionAtelier = 'horizonProfile' | 'poseSurfaces' | 'underlay' | 'environment';

/**
 * ACAL26 — traduit UNE section `{cle: valeur}` en hydratation partielle, avec les MÊMES
 * lecteurs que le boot (jamais une seconde logique). `horizonProfile` et `underlay` ne
 * vivent pas dans les couches du ctx (ils ont leur propre API : `shadingUi.setHorizonProfile`,
 * `semerFondDepuisDocument`) : ils rendent une hydratation vide, l'appelant les route.
 */
export function hydratationDeSection(cle: CleSectionAtelier, valeur: unknown): HydratationAtelier {
  const lu = lireCouchesDocument({ [cle]: valeur });
  if (cle === 'poseSurfaces') return { surfacesPose: lu.surfacesPose };
  if (cle === 'environment') return { environment: lu.environment };
  return {};
}

/** L'origine devis mémorisée par le boot (`applyDevisHydration`). */
export interface OrigineDevis {
  devisId: string | number | null;
  panelWatt: number | null;
  scenario: LayoutScenario | null;
}

/** Ce que le wrapper `onApiReady.serializeLayout` sait de l'atelier au moment d'écrire. */
export interface EtatSerialisationAtelier {
  devisOrigin: OrigineDevis | null;
  solarAccess: Pick<SerializeMeta, 'solarAccessByZone'> | null;
  setbacks: PerimeterSetbacks;
  horizonProfile: SerializeMeta['horizonProfile'] | null | undefined;
  modules: AffectationModules | null;
  coucheElectrique: Pick<CoucheElectrique, 'ecrireDansDocument'> | null;
}

/**
 * ACAL26 — compose la meta de sérialisation de l'atelier (extraite du wrapper
 * `onApiReady.serializeLayout`, roof-tool-pro11.ts). Les DEUX branches — document issu d'un
 * devis, document lead — portent la couche électrique : avant, aucune ne la passait, et un
 * onduleur posé disparaissait au premier enregistrement. Ce que l'appelant fournit
 * explicitement (`meta`) l'emporte toujours.
 */
export function composerMetaSerialisation(etat: EtatSerialisationAtelier, meta?: SerializeMeta): SerializeMeta {
  const commun: SerializeMeta = {
    ...(etat.solarAccess ?? {}),
    setbacksM: { ...etat.setbacks },
    ...(etat.horizonProfile ? { horizonProfile: etat.horizonProfile } : {}),
    modules: etat.modules,
    ...(etat.coucheElectrique ? { coucheElectrique: etat.coucheElectrique } : {}),
  };
  const o = etat.devisOrigin;
  if (!o) return { ...commun, ...(meta ?? {}) };
  return {
    source: 'devis',
    devisId: o.devisId,
    ...(o.panelWatt != null ? { panelWatt: o.panelWatt } : {}),
    ...(o.scenario ? { scenario: o.scenario } : {}),
    ...commun,
    ...(meta ?? {}),
  };
}

/** ACAL26 — le sérialiseur CÂBLÉ de l'atelier : `serializeLayout` + la meta composée. C'est
 *  ce que le wrapper `onApiReady.serializeLayout` appelle (et ce que les tests appellent). */
export function serialiserDocumentAtelier(
  ctx: Ctx,
  billKwh: number | null,
  etat: EtatSerialisationAtelier,
  meta?: SerializeMeta,
): SerializedLayout {
  return serializeLayout(ctx, billKwh, composerMetaSerialisation(etat, meta));
}
