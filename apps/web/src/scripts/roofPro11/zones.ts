/**
 * « Plusieurs zones » : instantané du résultat/géométrie de la zone active +
 * rendu du panneau de total agrégé. Extrait de roof-tool-pro11.ts (split
 * modulaire 2026-06-20) — comportement INCHANGÉ.
 *
 * Le RENDU 3D des autres zones (`appendOtherZones`, couplé à `buildZoneMeshes`)
 * reste dans roof-tool-pro11.ts tant que la scène n'est pas extraite.
 */
import { aggregateAreas, areaLabel, type AreaResult } from '../../lib/roofAreas';
import { annualSavingsMad } from '../../lib/estimatorBrainV2';
import { fmt, fmtMad, esc } from './dom';
import { type Ctx } from './context';
import { type AreaRecord } from './types';
import { type RoofShapePan, type RoofShapePreset } from './scene3d';
import { geodesicAreaM2, pointInPolygon, type LngLat } from '../../lib/roof';
import { type Obstacle } from '../../lib/obstacles';
import {
  centroideAnneau,
  dimensionsRectangleM,
  pivoterAnneau,
  pivoterPoint,
  redimensionnerRectangle,
} from './snap';
import { computePanStats, computeSiteStats, hasMultipleBuildings, htmlTableSite, type PanStat } from './panStats'; // CALX126
// CALX109/CALX110 câblage — le catalogue de modules de la société et le module posé sur
// CHAQUE pan. `moduleSelect.ts` est PUR (aucun DOM) : c'est ici, dans le panneau du pan, que
// le choix devient visible, et c'est de là qu'il repart vers le pavage et le document.
import {
  MODULE_PAR_DEFAUT_ATELIER,
  cotesDeModule,
  estRefus,
  lireModulesDisponibles,
  resoudreModuleDuPan,
  type CatalogueModules,
  type ModuleDisponible,
  type ModuleDocument,
  type SyntheseModules,
} from './moduleSelect';

/**
 * CAL56 — traduit les pans générés par `generateRoofShapePans` (scene3d.ts, géométrie pure)
 * en `AreaRecord[]` prêts à remplacer `ctx.areas` : un pan = une zone, exactement le même
 * objet que « + Ajouter une zone » crée à la main (mécanique multi-zones INCHANGÉE — chaque
 * pan reste ensuite éditable individuellement via le panneau « Zones »). `makeId` est injecté
 * (aucun Date.now()/Math.random() ici) pour rester pur et testable ; roofType = 'flat' pour
 * le préré 'flat', 'pitched' sinon (pente = `pitchDeg` saisi par l'utilisateur, inchangé — ce
 * module ne l'invente pas).
 */
export function buildAreasFromShape(
  pans: RoofShapePan[],
  shape: RoofShapePreset,
  pitchDeg: number,
  makeId: () => string,
): AreaRecord[] {
  return pans.map((pan) => ({
    id: makeId(),
    label: '',
    vertices: pan.vertices,
    obstacles: [],
    roofType: shape === 'flat' ? 'flat' : 'pitched',
    pitchDeg,
    facingAzimuthDeg: pan.facingAzimuthDeg,
    facingManual: shape !== 'flat',
    neededPanels: 0,
    neededAuto: true,
    result: null,
    renderPlan: null,
  }));
}

// ————————————————————————————————————————————————————————————————————————
// CALX97 — COTES EXACTES D'UN PAN ET ROTATION D'UN BLOC
//
// Un pan ne se modifiait qu'au glissé de ses sommets : aucune saisie de largeur/longueur,
// aucune rotation d'ensemble. Parité HelioScope (cotes exactes tapables + « Rotate Field
// Segments/Keepouts »). La géométrie est dans `snap.ts` ; ce bloc l'applique à un PAN —
// c'est-à-dire à son contour ET à ses obstacles — de façon PURE et testable.
//
// CE QUI SUIT LA ROTATION, ET CE QUI NE LA SUIT PAS : le CENTRE de chaque obstacle tourne
// autour du centroïde du pan, donc un obstacle reste au même endroit du toit. Son rectangle,
// lui, reste orienté nord-sud/est-ouest, parce que le document ne porte AUCUNE orientation
// d'obstacle (`lib/obstacles.ts` : `lengthM` = étendue nord-sud, `widthM` = est-ouest). On
// n'invente pas cette clé ici : ce serait un champ de document créé par une lane d'écran.
// ————————————————————————————————————————————————————————————————————————

/** La part d'un pan que CALX97 déplace : son contour et ses obstacles. */
export interface GeometriePan {
  vertices: LngLat[];
  obstacles: Obstacle[];
}

/** Verdict d'une transformation de pan — un refus NOMME le pan ET la raison. */
export type VerdictPan = { ok: true; geometrie: GeometriePan } | { ok: false; motif: string };

/**
 * CALX97 — fait pivoter un pan de `angleDeg` (sens horaire) autour du centroïde de son
 * contour : le contour ET les centres de ses obstacles suivent le même mouvement. Refus
 * NOMMÉ quand le contour n'a pas de quoi définir un centre, ou que l'angle est illisible.
 */
export function pivoterPan(pan: GeometriePan, angleDeg: number, nomDuPan: string): VerdictPan {
  if (!Array.isArray(pan?.vertices) || pan.vertices.length < 3) {
    return { ok: false, motif: `${nomDuPan} : rotation refusée — ce pan n’a pas encore de contour fermé.` };
  }
  if (!Number.isFinite(angleDeg)) {
    return { ok: false, motif: `${nomDuPan} : rotation refusée — saisissez un angle en degrés.` };
  }
  const centre = centroideAnneau(pan.vertices);
  if (!centre) {
    return { ok: false, motif: `${nomDuPan} : rotation refusée — le centre du pan est illisible.` };
  }
  const obstacles = (pan.obstacles ?? []).map((o) => {
    const c = pivoterPoint([o.centerLng, o.centerLat], angleDeg, centre);
    return { ...o, centerLng: c[0], centerLat: c[1] };
  });
  return { ok: true, geometrie: { vertices: pivoterAnneau(pan.vertices, angleDeg, centre), obstacles } };
}

/**
 * CALX97 — repose un pan RECTANGULAIRE aux cotes saisies, autour de son centroïde. Les
 * obstacles ne bougent PAS : ils sont posés à un endroit réel du toit, et les décaler avec
 * les cotes inventerait une position que personne n'a relevée. Refus NOMMÉ (avec le nom du
 * pan) quand le contour n'est pas un quadrilatère ou qu'une cote manque.
 */
export function redimensionnerPan(
  pan: GeometriePan,
  largeurM: number,
  longueurM: number,
  nomDuPan: string,
): VerdictPan {
  const verdict = redimensionnerRectangle(pan?.vertices ?? [], largeurM, longueurM);
  if (!verdict.ok) return { ok: false, motif: `${nomDuPan} : ${verdict.motif}` };
  return { ok: true, geometrie: { vertices: verdict.anneau, obstacles: (pan.obstacles ?? []).map((o) => ({ ...o })) } };
}

// ————————————————————————————————————————————————————————————————————————
// CALX98 — DUPLIQUER UN PAN AVEC SES OBSTACLES ET SES RÉGLAGES
//
// « + Ajouter une zone » crée toujours une zone VIDE, et la duplication n'existait que pour
// les obstacles — alors qu'une toiture industrielle répète le même sied dix fois. Parité
// HelioScope (« Clone designs »). PUR et testable : aucun DOM, aucune carte.
//
// ZÉRO CHIFFRE INVENTÉ : le décalage de la copie est SAISI. Tant qu'il ne l'est pas, la
// duplication est REFUSÉE avec son motif — on ne pose jamais la copie « un peu plus loin »
// d'une distance que personne n'a demandée.
// ————————————————————————————————————————————————————————————————————————

/** Verdict d'une duplication de pan — un refus NOMME toujours sa raison. */
export type VerdictDuplication = { ok: true; zone: AreaRecord } | { ok: false; motif: string };

/**
 * CALX98 — motif qui EMPÊCHE la duplication au pas saisi, ou `null` quand le pas est
 * exploitable. L'écran s'en sert pour garder le bouton inactif ET afficher la raison.
 */
export function motifPasDuplication(pasM: number): string | null {
  if (!Number.isFinite(pasM) || pasM <= 0) {
    return 'Saisissez le décalage de la copie, en mètres : aucun décalage n’est supposé.';
  }
  return null;
}

/**
 * CALX98 — copie un pan dans une zone NEUVE, décalée du pas SAISI. Sont recopiés : le
 * contour, les obstacles (avec de nouveaux identifiants, dérivés de l'id de la zone, donc
 * sans collision), `roofType`, `pitchDeg`, `facingAzimuthDeg`, `facingManual`, `edges` et
 * `buildingId`. Ne sont PAS recopiés : le résultat et le plan de rendu — la copie n'a rien
 * de calculé tant que le moteur n'a pas tourné, et publier le compte de l'original serait un
 * chiffre inventé.
 *
 * Le décalage est une TRANSLATION RIGIDE vers l'est (même convention que la duplication
 * d'obstacle, CAL73) : le même écart de longitude, calculé à la latitude du centroïde, est
 * appliqué à TOUS les points — contour et obstacles — pour que la copie garde exactement la
 * forme de l'original.
 */
export function dupliquerPan(source: AreaRecord, nouvelId: string, pasM: number): VerdictDuplication {
  const motif = motifPasDuplication(pasM);
  if (motif) return { ok: false, motif };
  if (!source || !Array.isArray(source.vertices) || source.vertices.length < 3) {
    return { ok: false, motif: 'Duplication refusée : ce pan n’a pas encore de contour fermé.' };
  }
  const centre = centroideAnneau(source.vertices);
  if (!centre) return { ok: false, motif: 'Duplication refusée : le centre du pan est illisible.' };
  const cosLat = Math.max(1e-6, Math.cos(centre[1] * ZONE_DEG2RAD));
  const dLng = pasM / (ZONE_DEG2M * cosLat);
  return {
    ok: true,
    zone: {
      id: nouvelId,
      label: '',
      vertices: source.vertices.map(([lng, lat]) => [lng + dLng, lat] as LngLat),
      obstacles: (source.obstacles ?? []).map((o, i) => ({
        ...o,
        id: `${nouvelId}-obs-${i + 1}`,
        centerLng: o.centerLng + dLng,
      })),
      roofType: source.roofType,
      pitchDeg: source.pitchDeg,
      facingAzimuthDeg: source.facingAzimuthDeg,
      facingManual: source.facingManual,
      neededPanels: 0,
      neededAuto: true,
      result: null,
      renderPlan: null,
      ...(source.buildingId ? { buildingId: source.buildingId } : {}),
      ...(source.edges ? { edges: source.edges.map((e) => ({ ...e })) } : {}),
    },
  };
}

/** CALX98 — identifiant de zone NEUF, dans un espace de noms (`area-copie-N`) que le
 *  compteur `area-<n>` de l'entrée ne produit jamais : aucune collision possible. */
export function idZoneCopie(existants: readonly { id: string }[]): string {
  const pris = new Set((existants ?? []).map((a) => a.id));
  let n = 1;
  while (pris.has(`area-copie-${n}`)) n++;
  return `area-copie-${n}`;
}

export interface Zones {
  liveActiveResult: () => AreaResult | null;
  snapshotActiveAreaResult: () => void;
  snapshotActiveAreaGeometry: () => void;
  syncAddAreaButton: () => void;
  renderAreasPanel: () => void;
  /** CAL59 — assigne (ou efface, chaîne vide) le bâtiment d'une zone, puis re-rend le
   *  panneau. N'affecte ni le résultat ni la géométrie de la zone. */
  setAreaBuilding: (id: string, buildingId: string) => void;
  /** CALX97 — fait pivoter le pan ACTIF (contour + obstacles) de l'angle saisi. Renvoie
   *  false et n'applique RIEN quand c'est refusé ; le motif nomme le pan. */
  pivoterPanActif: (angleDeg: number) => boolean;
  /** CALX97 — repose le pan ACTIF aux cotes saisies (pan rectangulaire seulement). */
  redimensionnerPanActif: (largeurM: number, longueurM: number) => boolean;
  /** CALX98 — duplique le pan ACTIF (contour, obstacles et réglages) dans une zone neuve
   *  décalée du pas SAISI. Renvoie false et ne crée RIEN sans pas saisi. */
  dupliquerPanActif: (pasM: number) => boolean;
  /** CALX109/CALX110 câblage — pose le modèle de module `moduleId` sur le pan ACTIF (chaîne
   *  vide = retour au module par défaut de l'atelier). Renvoie false et n'écrit RIEN quand le
   *  modèle est grisé, inconnu, ou sans cotes — le refus NOMME le pan et le motif. */
  choisirModuleDuPanActif: (moduleId: string | null | undefined) => boolean;
}

/**
 * CALX97 — crochets d'écran OPTIONNELS. Absents, `createZones` se comporte EXACTEMENT comme
 * avant (le seul appelant, `roof-tool-pro11.ts`, n'en passe aucun aujourd'hui) ; fournis,
 * une transformation de pan redessine et re-pave immédiatement.
 */
export interface ZonesDeps {
  /** Re-dessine la ligne + les pastilles de sommets du pan actif. */
  redrawTrace?: () => void;
  /** Re-dessine le calque des obstacles du pan actif. */
  redrawObstacles?: () => void;
  /** Re-pavage + production après un changement de géométrie. */
  recalc?: () => void;
  /** Bandeau de statut (refus nommés, confirmations). */
  setStatus?: (msg: string) => void;
}

/** CAL84 — libellé d'un bâtiment (repli « Bâtiment sans id » pour un groupe sans
 *  `buildingId` mélangé à des zones qui en portent un — cas limite, ne devrait pas
 *  arriver en pratique une fois CAL59 câblé, mais ne doit jamais planter l'affichage). */
function buildingLabel(buildingId: string | null): string {
  return buildingId ? buildingId : 'Bâtiment sans id';
}

export function createZones(ctx: Ctx, deps: ZonesDeps = {}): Zones {
  // CAL84 — table des statistiques par pan, créée UNE fois si l'hôte ne la fournit pas déjà
  // (même pattern que le sélecteur de type d'obstacle, obstaclesUi.ts `ensureTypePicker`) :
  // aucune page n'a à être modifiée pour l'afficher.
  function ensureStatsTable(): HTMLElement | null {
    const existing = document.getElementById('rp9-areas-stats');
    if (existing) return existing;
    const { areasWindowEl } = ctx.dom;
    if (!areasWindowEl || typeof document.createElement !== 'function') return null;
    const el = document.createElement('div');
    el.id = 'rp9-areas-stats';
    el.className = 'mt-3 overflow-x-auto';
    areasWindowEl.appendChild(el);
    return el;
  }

  /** Résultat VIVANT de la zone active (gagnant de l'optimiseur courant) — plat
   *  (`liveResult.winner`) ou pente (`pitchedLiveResult.winner`). null si rien de calculé
   *  ou pose nulle (zone sans panneaux). */
  function liveActiveResult(): AreaResult | null {
    if (!ctx.closed || ctx.vertices.length < 3) return null;
    if (ctx.roofType === 'pitched') {
      const res = ctx.pitchedLiveResult;
      if (!res || res.northFacing) return null;
      const w = res.winner;
      if (w.placedCount <= 0) return null;
      return { panels: w.placedCount, kwc: w.kwc, annualKwh: w.annualKwh, savingsLow: w.savingsLow, savingsHigh: w.savingsHigh };
    }
    const res = ctx.liveResult;
    if (!res) return null;
    const w = res.winner;
    if (w.placedCount <= 0) return null;
    return { panels: w.placedCount, kwc: w.kwc, annualKwh: w.annualKwh, savingsLow: w.savingsLow, savingsHigh: w.savingsHigh };
  }

  /** Écrit l'instantané du résultat vivant dans l'enregistrement de la zone active. */
  function snapshotActiveAreaResult() {
    const a = ctx.activeArea();
    if (a) a.result = liveActiveResult();
  }

  /** Capture la GÉOMÉTRIE + l'état d'édition courants de la zone active dans son
   *  enregistrement (sans toucher au résultat, géré par le snapshot ci-dessus). */
  function snapshotActiveAreaGeometry() {
    const a = ctx.activeArea();
    if (!a) return;
    a.vertices = [...ctx.vertices];
    a.obstacles = ctx.obstacles.map((o) => ({ ...o }));
    a.roofType = ctx.roofType;
    a.pitchDeg = ctx.pitchDeg;
    a.facingAzimuthDeg = ctx.facingAzimuthDeg;
    a.facingManual = ctx.facingManual; // W106 — l'override manuel par zone persiste
    a.neededPanels = ctx.neededPanels;
    a.neededAuto = ctx.neededAuto;
  }

  /** Active/désactive le bouton « + Ajouter une zone » : autorisé seulement quand la
   *  zone active est FERMÉE (un tracé valide existe). */
  function syncAddAreaButton() {
    const { addAreaBtn } = ctx.dom;
    if (addAreaBtn) addAreaBtn.disabled = !ctx.closed || ctx.vertices.length < 3;
  }

  /** Rend le panneau « Zones » : total agrégé (zone active = résultat LIVE, pas le snapshot
   *  potentiellement périmé) + une ligne par zone. Masqué tant qu'aucune zone n'a de résultat. */
  function renderAreasPanel() {
    syncAddAreaButton();
    const { areasWindowEl, areasListEl, areasTotalPanelsEl, areasTotalKwcEl, areasTotalProdEl, areasTotalSavingsEl } = ctx.dom;
    if (!areasWindowEl) return;
    const areas = ctx.areas;
    const activeAreaId = ctx.activeAreaId;
    const liveActive = liveActiveResult();
    // Résultats agrégés : la zone active prend son résultat LIVE, les autres leur snapshot.
    const results = areas.map((a) => (a.id === activeAreaId ? liveActive : a.result));
    const anyResult = results.some((r) => r != null);
    areasWindowEl.hidden = !anyResult;
    if (!anyResult) return;
    // WB20 — toutes les zones résolvent contre la MÊME facture globale (pas une part
    // par zone) : chaque `r.savings*` est déjà plafonné à TOUTE la facture, donc les
    // sommer sur-compterait jusqu'à N× sur un toit à N zones. On repasse la cible
    // annuelle globale (facture) à `aggregateAreas` pour qu'elle recalcule UNE seule
    // économie plafonnée à partir du kWh produit total.
    const targetAnnualKwh = ctx.roofType === 'pitched' ? ctx.pitchedRec?.targetAnnualKwh : ctx.rec?.targetAnnualKwh;
    const total = aggregateAreas(results, targetAnnualKwh, annualSavingsMad);
    if (areasTotalPanelsEl) areasTotalPanelsEl.textContent = `${fmt(total.panels)} × 720 W`;
    // W97 §2 — 2 décimales, pas 1 : kwc = panneaux × 0,72 tient toujours en 2
    // décimales exactes, donc le total agrégé et chaque carte de zone (rp9-reco-kwc,
    // même règle) affichent leur valeur RÉELLE sans arrondi indépendant — la somme
    // des zones affichées == le total affiché, par construction (cf. optimizer.ts).
    if (areasTotalKwcEl) areasTotalKwcEl.textContent = `${total.kwc.toLocaleString('fr-FR', { maximumFractionDigits: 2 })} kWc`;
    if (areasTotalProdEl) areasTotalProdEl.textContent = total.annualKwh > 0 ? `${fmt(Math.round(total.annualKwh))} kWh/an` : '—';
    if (areasTotalSavingsEl) areasTotalSavingsEl.textContent = total.savingsHigh > 0 ? `${fmtMad(total.savingsLow)} – ${fmtMad(total.savingsHigh)}/an` : '—';

    // CAL59 — statistiques par pan + totaux par bâtiment (colonnes toutes CALCULÉES).
    // CALX110 câblage — 3ᵉ argument : le MODULE de chaque pan. Sans lui, deux modèles posés
    // sur deux pans rendaient le même kWc (`nombre × 720 W` partout) ; avec lui, le kWc d'un
    // pan vaut `nombre × la puissance de SON module` et l'occupation se mesure sur SON
    // empreinte. Un pan sans choix rend `null` ⇒ colonnes identiques à aujourd'hui.
    const stats = computePanStats(areas, (a) => (a.id === activeAreaId ? liveActive : a.result), moduleDuPan);
    const multiBuilding = hasMultipleBuildings(stats);

    if (areasListEl) {
      const rowHtml = (a: AreaRecord, i: number): string => {
        const r = a.id === activeAreaId ? liveActive : a.result;
        const active = a.id === activeAreaId;
        const panels = r ? fmt(r.panels) : '—';
        const kwc = r ? `${r.kwc.toLocaleString('fr-FR', { maximumFractionDigits: 2 })} kWc` : 'à tracer';
        const rowClass = active
          ? 'border-brass-400 bg-brass-400/10'
          : 'border-white/10 bg-nuit-900/40';
        const delBtn =
          areas.length > 1
            ? `<button type="button" data-area-del="${a.id}" aria-label="Supprimer ${esc(a.label)}" class="border border-alert-300/60 px-2.5 py-1 text-xs font-semibold text-alert-300 transition-colors hover:bg-alert-300/10">×</button>`
            : '';
        const viewBtn = active
          ? `<span class="text-xs font-semibold text-brass-300">● active</span>`
          : `<button type="button" data-area-select="${a.id}" class="border border-white/25 px-2.5 py-1 text-xs font-semibold text-lune-soft transition-colors hover:border-brass-400 hover:text-brass-300">Voir</button>`;
        // CAL59 — saisie du bâtiment : un input LIBRE (l'utilisateur nomme ses bâtiments,
        // aucune liste imposée) ; vide = bâtiment unique, comportement historique.
        const buildingInput = `<input type="text" data-area-building="${a.id}" value="${esc(a.buildingId ?? '')}"
          placeholder="bâtiment" aria-label="Bâtiment de ${esc(a.label || areaLabel(i))}"
          class="w-24 border border-white/15 bg-nuit-900/60 px-1.5 py-0.5 text-[11px] text-lune-soft focus:border-brass-400 focus:outline-none" />`;
        return `<li class="flex flex-wrap items-center gap-x-3 gap-y-1 border ${rowClass} p-3 text-sm" data-area-row="${a.id}">
          <span class="font-semibold text-white">${esc(areaLabel(i))}</span>
          <span class="text-xs text-lune-faint">${panels} panneaux · ${kwc}</span>
          ${buildingInput}
          <span class="ml-auto flex items-center gap-2">${viewBtn}${delBtn}</span>
        </li>`;
      };
      if (!multiBuilding) {
        // CAL59 — aucune zone ne porte de `buildingId` : liste plate, octet pour octet
        // identique au comportement historique (aucun sous-total redondant).
        areasListEl.innerHTML = areas.map((a, i) => rowHtml(a, i)).join('');
      } else {
        // CAL59 — un calepinage multi-bâtiments : une ligne d'en-tête de sous-total PAR
        // bâtiment (panneaux/kWc CALCULÉS, jamais saisis), suivie des zones du groupe.
        const indexOf = new Map(areas.map((a, i) => [a.id, i]));
        areasListEl.innerHTML = stats.byBuilding
          .map((b) => {
            const rows = areas.filter((a) => (a.buildingId ?? null) === b.buildingId);
            const header = `<li class="border border-white/20 bg-nuit-900/60 px-3 py-2 text-xs font-semibold uppercase tracking-wide text-lune-faint" data-building-header="${esc(b.buildingId ?? '')}">
              ${esc(buildingLabel(b.buildingId))} — ${fmt(b.panels)} panneaux · ${b.kwc.toLocaleString('fr-FR', { maximumFractionDigits: 2 })} kWc
            </li>`;
            return header + rows.map((a) => rowHtml(a, indexOf.get(a.id) ?? 0)).join('');
          })
          .join('');
      }
    }

    // CAL84 — tableau par pan (modules/kWc/orientation/pente/surface utile/occupation),
    // totalisé par bâtiment puis par site. Masqué s'il n'y a qu'un seul pan sans intérêt
    // de tableau… non : affiché dès qu'un résultat existe (même règle que le reste du
    // panneau), pour que la somme des lignes reste visible et vérifiable.
    const statsEl = ensureStatsTable();
    if (statsEl) renderStatsTable(statsEl, stats.pans, multiBuilding);

    // CALX97 — les cotes affichées suivent le pan actif (lues, jamais devinées).
    syncGeometryPanel();
    // CALX109/CALX110 câblage — le sélecteur suit le pan actif, et la mention NOMME ce qui
    // est réellement posé (le module par défaut tant que rien n'est choisi, « plusieurs
    // modèles » dès que les pans divergent).
    syncModulePicker(stats.modules);
    if (statsEl) statsEl.insertAdjacentHTML('beforeend', htmlTableSite(computeSiteStats(stats, ctx.surfacesPose))); // CALX126 — totaux du site : pans de toit ET surfaces de pose, une ligne par surface, un total par bâtiment
  }

  /** Rend le tableau CAL84 : une ligne par pan, colonnes toutes calculées. */
  function renderStatsTable(el: HTMLElement, pans: PanStat[], multiBuilding: boolean): void {
    const fmtPct = (r: number | null) => (r == null ? '—' : `${Math.round(r * 100)} %`);
    const fmtDeg = (v: number | null) => (v == null ? '—' : `${Math.round(v)}°`);
    const rows = pans
      .map(
        (p) => `<tr data-pan-stat="${esc(p.id)}">
          <td class="px-2 py-1 text-white">${esc(p.label || p.id)}</td>
          ${multiBuilding ? `<td class="px-2 py-1 text-lune-faint">${esc(buildingLabel(p.buildingId))}</td>` : ''}
          <td class="px-2 py-1 text-right">${p.panels ? fmt(p.panels) : `0 <span class="text-lune-faint">(${esc(p.zeroReason)})</span>`}</td>
          <td class="px-2 py-1 text-right">${p.kwc.toLocaleString('fr-FR', { maximumFractionDigits: 2 })}</td>
          <td class="px-2 py-1 text-right">${fmtDeg(p.azimuthDeg)}</td>
          <td class="px-2 py-1 text-right">${fmtDeg(p.pitchDeg)}</td>
          <td class="px-2 py-1 text-right">${p.areaM2 > 0 ? Math.round(p.areaM2) : '—'}</td>
          <td class="px-2 py-1 text-right">${fmtPct(p.occupancyRate)}</td>
        </tr>`,
      )
      .join('');
    el.innerHTML = `<table class="w-full min-w-[520px] border-collapse text-xs text-lune-soft">
      <thead>
        <tr class="border-b border-white/15 text-left text-[11px] uppercase tracking-wide text-lune-faint">
          <th class="px-2 py-1">Pan</th>
          ${multiBuilding ? '<th class="px-2 py-1">Bâtiment</th>' : ''}
          <th class="px-2 py-1 text-right">Modules</th>
          <th class="px-2 py-1 text-right">kWc</th>
          <th class="px-2 py-1 text-right">Azimut</th>
          <th class="px-2 py-1 text-right">Pente</th>
          <th class="px-2 py-1 text-right">Surface m²</th>
          <th class="px-2 py-1 text-right">Occupation</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>`;
  }

  // ————————————————————————————————————————————————————————————————————
  // CALX97 — panneau « Cotes et rotation du pan », créé ICI si l'hôte ne le fournit pas
  // (même patron qu'`ensureStatsTable`) : aucune page n'a à être modifiée. Il agit sur le
  // pan ACTIF — celui qui est à l'écran — et le NOMME dans chaque message.
  // ————————————————————————————————————————————————————————————————————
  function ensureGeometryPanel(): HTMLElement | null {
    const existing = document.getElementById('rp9-pan-geometry');
    if (existing) return existing;
    const { areasWindowEl } = ctx.dom;
    if (!areasWindowEl || typeof document.createElement !== 'function') return null;
    const el = document.createElement('div');
    el.id = 'rp9-pan-geometry';
    el.className = 'rp9-pan-geometry mt-3 flex flex-wrap items-center gap-2 text-xs';
    el.innerHTML =
      `<span class="font-semibold" id="rp9-pan-geometry-nom"></span>` +
      `<label class="inline-flex items-center gap-1" for="rp9-pan-largeur">Largeur (m)` +
      `<input type="text" id="rp9-pan-largeur" class="rp9-input w-20" inputmode="decimal" /></label>` +
      `<label class="inline-flex items-center gap-1" for="rp9-pan-longueur">Longueur (m)` +
      `<input type="text" id="rp9-pan-longueur" class="rp9-input w-20" inputmode="decimal" /></label>` +
      `<button type="button" id="rp9-pan-coter" class="rp9-btn">Appliquer les cotes</button>` +
      `<label class="inline-flex items-center gap-1" for="rp9-pan-rotation">Rotation (°)` +
      `<input type="text" id="rp9-pan-rotation" class="rp9-input w-20" inputmode="decimal" /></label>` +
      `<button type="button" id="rp9-pan-pivoter" class="rp9-btn">Pivoter le pan</button>` +
      `<span id="rp9-pan-geometry-erreur" class="text-alert-300" role="alert" hidden></span>`;
    areasWindowEl.appendChild(el);
    return el;
  }
  const geometryPanelEl = ensureGeometryPanel();
  const panNomEl = document.getElementById('rp9-pan-geometry-nom');
  const panLargeurEl = document.getElementById('rp9-pan-largeur') as HTMLInputElement | null;
  const panLongueurEl = document.getElementById('rp9-pan-longueur') as HTMLInputElement | null;
  const panRotationEl = document.getElementById('rp9-pan-rotation') as HTMLInputElement | null;
  const panErreurEl = document.getElementById('rp9-pan-geometry-erreur');

  /** Nombre à la française (virgule décimale tolérée), comme partout dans l'atelier. */
  const nombreSaisi = (s: string | null | undefined): number =>
    parseFloat((s ?? '').replace(/\s/g, '').replace(',', '.'));

  /** Nom du pan ACTIF, tel qu'il est écrit dans la liste des zones. */
  function nomDuPanActif(): string {
    const i = ctx.areas.findIndex((a) => a.id === ctx.activeAreaId);
    const a = i >= 0 ? ctx.areas[i] : undefined;
    return a?.label || areaLabel(i >= 0 ? i : 0);
  }

  /** Affiche (ou efface) un refus NOMMÉ, dans le panneau ET dans le bandeau de statut. */
  function direRefusGeometrie(motif: string | null) {
    if (panErreurEl) {
      panErreurEl.textContent = motif ?? '';
      panErreurEl.hidden = !motif;
    }
    if (motif) deps.setStatus?.(motif);
  }

  /** Applique une géométrie transformée au pan ACTIF (contour + obstacles vivants). */
  function appliquerAuPanActif(geometrie: GeometriePan) {
    ctx.pushWorkshopHistory?.(); // CAL100 — annulable comme le reste de l'atelier
    ctx.vertices.splice(0, ctx.vertices.length, ...geometrie.vertices);
    ctx.obstacles.splice(0, ctx.obstacles.length, ...geometrie.obstacles);
    snapshotActiveAreaGeometry(); // l'enregistrement de la zone suit le pan vivant
    deps.redrawTrace?.();
    deps.redrawObstacles?.();
    deps.recalc?.();
    renderAreasPanel();
  }

  function pivoterPanActif(angleDeg: number): boolean {
    const verdict = pivoterPan(
      { vertices: ctx.vertices, obstacles: ctx.obstacles },
      angleDeg,
      nomDuPanActif(),
    );
    if (!verdict.ok) {
      direRefusGeometrie(verdict.motif);
      return false;
    }
    direRefusGeometrie(null);
    appliquerAuPanActif(verdict.geometrie);
    deps.setStatus?.(`${nomDuPanActif()} pivoté de ${angleDeg}° — ses obstacles ont suivi.`);
    return true;
  }

  function redimensionnerPanActif(largeurM: number, longueurM: number): boolean {
    const verdict = redimensionnerPan(
      { vertices: ctx.vertices, obstacles: ctx.obstacles },
      largeurM,
      longueurM,
      nomDuPanActif(),
    );
    if (!verdict.ok) {
      direRefusGeometrie(verdict.motif);
      return false;
    }
    direRefusGeometrie(null);
    appliquerAuPanActif(verdict.geometrie);
    deps.setStatus?.(`${nomDuPanActif()} reposé aux cotes saisies — son centre n’a pas bougé.`);
    return true;
  }

  /** Remplit le panneau avec les cotes RÉELLES du pan actif (jamais une cote devinée). */
  function syncGeometryPanel() {
    if (!geometryPanelEl) return;
    geometryPanelEl.hidden = !ctx.closed || ctx.vertices.length < 3;
    if (geometryPanelEl.hidden) return;
    if (panNomEl) panNomEl.textContent = nomDuPanActif();
    const dims = dimensionsRectangleM(ctx.vertices);
    const fmtDim = (v: number) => v.toLocaleString('fr-FR', { maximumFractionDigits: 2 });
    if (panLargeurEl && document.activeElement !== panLargeurEl) {
      panLargeurEl.value = dims ? fmtDim(dims.largeurM) : '';
      // Pan non rectangulaire : les cotes n'existent pas, on ne les invente pas.
      panLargeurEl.disabled = !dims;
    }
    if (panLongueurEl && document.activeElement !== panLongueurEl) {
      panLongueurEl.value = dims ? fmtDim(dims.longueurM) : '';
      panLongueurEl.disabled = !dims;
    }
    if (!dims) {
      direRefusGeometrie(
        `${nomDuPanActif()} : la saisie largeur/longueur ne s’applique qu’à un pan à 4 côtés. La rotation, elle, reste disponible.`,
      );
    }
  }

  geometryPanelEl?.addEventListener('click', (e) => {
    const cible = (e.target as HTMLElement).closest<HTMLElement>('button');
    if (cible?.id === 'rp9-pan-coter') {
      redimensionnerPanActif(nombreSaisi(panLargeurEl?.value), nombreSaisi(panLongueurEl?.value));
    } else if (cible?.id === 'rp9-pan-pivoter') {
      pivoterPanActif(nombreSaisi(panRotationEl?.value));
    }
  });

  // ————————————————————————————————————————————————————————————————————
  // CALX98 — bouton « Dupliquer ce pan » + son pas SAISI, créés ICI si l'hôte ne les
  // fournit pas. Le champ part VIDE et le bouton reste INACTIF tant qu'il l'est, avec le
  // motif affiché : aucun décalage n'est supposé.
  // ————————————————————————————————————————————————————————————————————
  function ensureDuplicatePanel(): HTMLElement | null {
    const existing = document.getElementById('rp9-pan-duplicate');
    if (existing) return existing;
    const { areasWindowEl } = ctx.dom;
    if (!areasWindowEl || typeof document.createElement !== 'function') return null;
    const el = document.createElement('div');
    el.id = 'rp9-pan-duplicate';
    el.className = 'rp9-pan-duplicate mt-2 flex flex-wrap items-center gap-2 text-xs';
    el.innerHTML =
      `<label class="inline-flex items-center gap-1" for="rp9-pan-dup-pas">Décalage de la copie (m)` +
      `<input type="text" id="rp9-pan-dup-pas" class="rp9-input w-20" inputmode="decimal" value="" /></label>` +
      `<button type="button" id="rp9-pan-dup" class="rp9-btn" disabled>Dupliquer ce pan</button>` +
      `<span id="rp9-pan-dup-motif" class="text-alert-300" role="status"></span>`;
    areasWindowEl.appendChild(el);
    return el;
  }
  const duplicatePanelEl = ensureDuplicatePanel();
  const dupPasEl = document.getElementById('rp9-pan-dup-pas') as HTMLInputElement | null;
  const dupBtnEl = document.getElementById('rp9-pan-dup') as HTMLButtonElement | null;
  const dupMotifEl = document.getElementById('rp9-pan-dup-motif');

  /** CALX98 — le bouton suit le pas saisi : inactif tant qu'il manque, motif affiché. */
  function syncDuplicateButton() {
    const motif = motifPasDuplication(nombreSaisi(dupPasEl?.value));
    if (dupBtnEl) dupBtnEl.disabled = motif != null;
    if (dupMotifEl) dupMotifEl.textContent = motif ?? '';
  }

  function dupliquerPanActif(pasM: number): boolean {
    const source = ctx.activeArea();
    if (!source) return false;
    // La zone active vit dans `ctx` : on fige sa géométrie avant de la recopier.
    snapshotActiveAreaGeometry();
    const verdict = dupliquerPan(source, idZoneCopie(ctx.areas), pasM);
    if (!verdict.ok) {
      if (dupMotifEl) dupMotifEl.textContent = verdict.motif;
      deps.setStatus?.(verdict.motif);
      return false;
    }
    ctx.pushWorkshopHistory?.(); // CAL100 — annulable comme le reste de l'atelier
    ctx.areas.push(verdict.zone);
    renderAreasPanel();
    deps.setStatus?.(
      `${nomDuPanActif()} dupliqué — la copie porte ses ${verdict.zone.obstacles.length} obstacle(s) et ses réglages. Ouvrez-la avec « Voir ».`,
    );
    return true;
  }

  dupPasEl?.addEventListener('input', syncDuplicateButton);
  dupPasEl?.addEventListener('change', syncDuplicateButton);
  duplicatePanelEl?.addEventListener('click', (e) => {
    if ((e.target as HTMLElement).closest<HTMLElement>('#rp9-pan-dup')) {
      dupliquerPanActif(nombreSaisi(dupPasEl?.value));
    }
  });
  syncDuplicateButton(); // état initial : champ vide ⇒ bouton inactif + motif affiché

  // ————————————————————————————————————————————————————————————————————
  // CALX109/CALX110 câblage — LE SÉLECTEUR DE MODULE DU PAN ACTIF
  //
  // LE CONSTAT. `moduleSelect.ts` savait déjà lire le catalogue de la société, résoudre le
  // module d'un pan et écrire le tout dans le document — mais RIEN ne permettait de choisir :
  // aucun sélecteur n'existait, donc aucun pan ne portait jamais de `moduleId` et l'atelier
  // ne pavait que son module par défaut. Ce bloc crée le contrôle LUI-MÊME quand la page
  // hôte ne le fournit pas (même patron qu'`ensureStatsTable` / `ensureGeometryPanel`,
  // d'origine `obstaclesUi.ts ensureTypePicker`) : aucune page n'a à être modifiée.
  //
  // CE QU'IL MONTRE, ET CE QU'IL REFUSE. La liste s'ouvre TOUJOURS sur le module par défaut
  // de l'atelier, NOMMÉ — c'est ce qui est posé tant que personne n'a choisi. Viennent
  // ensuite les modèles CHOISISSABLES, puis les modèles GRISÉS (`disabled`) avec le motif du
  // SERVEUR : une fiche produit incomplète reste VISIBLE, sinon on la cherche en vain. Un
  // refus nomme le pan et le modèle, s'affiche À CÔTÉ du sélecteur et dans le bandeau de
  // statut — jamais un « non enregistré » générique. Catalogue vide ⇒ le motif du serveur
  // est dit tel quel ; aucune cote n'est inventée, jamais.
  // ————————————————————————————————————————————————————————————————————

  /** CALX109 — le catalogue de la société, lu UNE fois : `ctx.opts` est figé au boot. */
  const catalogueAtelier: CatalogueModules = lireModulesDisponibles(ctx.opts?.modulesDisponibles);

  /** Le motif d'un modèle GRISÉ : celui du serveur d'abord, sinon celui que les cotes
   *  manquantes dictent (`cotesDeModule` NOMME déjà le champ). Jamais un motif inventé. */
  function motifGrise(g: ModuleDisponible): string {
    if (g.motif && g.motif.trim()) return g.motif.trim();
    const refus = cotesDeModule(g.module);
    return estRefus(refus) ? refus.message : 'fiche produit incomplète';
  }

  function ensureModulePicker(): HTMLElement | null {
    const existing = document.getElementById('rp9-pan-module');
    if (existing) return existing;
    const { areasWindowEl } = ctx.dom;
    if (!areasWindowEl || typeof document.createElement !== 'function') return null;
    const el = document.createElement('div');
    el.id = 'rp9-pan-module';
    el.className = 'rp9-pan-module mt-2 flex flex-wrap items-center gap-2 text-xs';
    const options = [
      `<option value="">${esc(MODULE_PAR_DEFAUT_ATELIER.libelle)}</option>`,
      ...catalogueAtelier.choisissables.map(
        (m) => `<option value="${esc(m.id)}">${esc(m.libelle)}</option>`,
      ),
      ...catalogueAtelier.grises.map(
        (g) => `<option value="${esc(g.module.id)}" disabled data-module-grise="1">${esc(g.module.libelle)} — ${esc(motifGrise(g))}</option>`,
      ),
    ].join('');
    el.innerHTML =
      `<label class="inline-flex items-center gap-1" for="rp9-pan-module-select">Module du pan` +
      `<select id="rp9-pan-module-select" class="rp9-input">${options}</select></label>` +
      `<span id="rp9-pan-module-mention" class="text-lune-faint"></span>` +
      `<span id="rp9-pan-module-erreur" class="text-alert-300" role="alert" hidden></span>`;
    areasWindowEl.appendChild(el);
    return el;
  }
  const modulePickerEl = ensureModulePicker();
  const moduleSelectEl = document.getElementById('rp9-pan-module-select') as HTMLSelectElement | null;
  const moduleMentionEl = document.getElementById('rp9-pan-module-mention');
  const moduleErreurEl = document.getElementById('rp9-pan-module-erreur');

  /** Affiche (ou efface) un refus NOMMÉ, à côté du sélecteur ET dans le bandeau de statut. */
  function direRefusModule(motif: string | null) {
    if (moduleErreurEl) {
      moduleErreurEl.textContent = motif ?? '';
      moduleErreurEl.hidden = !motif;
    }
    if (motif) deps.setStatus?.(motif);
  }

  /**
   * CALX109/CALX110 — le module RÉSOLU d'un pan, pour `computePanStats`.
   *
   * Un pan SANS choix rend `null` — et pas le module par défaut : c'est ce qui garantit que
   * tant que personne n'a choisi, le tableau par pan affiche exactement les chiffres
   * d'aujourd'hui (kWc du résultat de zone, empreinte de l'étude), octet pour octet. Un
   * `moduleId` devenu introuvable rend `null` aussi : on n'invente pas une cote à sa place
   * (le refus, lui, est dit par `syncModulePicker`).
   */
  function moduleDuPan(a: AreaRecord): ModuleDocument | null {
    if (!a.moduleId) return null;
    const module = resoudreModuleDuPan(catalogueAtelier.choisissables, a.moduleId);
    if (estRefus(module)) return null;
    return estRefus(cotesDeModule(module)) ? null : module;
  }

  /** CALX109 — le sélecteur suit le pan ACTIF ; la mention NOMME ce qui est posé. */
  function syncModulePicker(synthese?: SyntheseModules) {
    if (!modulePickerEl) return;
    const a = ctx.activeArea();
    modulePickerEl.hidden = !a;
    if (!a) return;
    if (moduleSelectEl && document.activeElement !== moduleSelectEl) {
      moduleSelectEl.value = a.moduleId ?? '';
      // Un `moduleId` que le catalogue ne porte plus ne peut pas être sélectionné : le
      // <select> retombe sur le défaut tout seul. On le DIT, plutôt que de laisser croire
      // que ce pan est revenu au module par défaut de son plein gré.
      if (a.moduleId && moduleSelectEl.value !== a.moduleId) {
        direRefusModule(
          `${nomDuPanActif()} : le module « ${a.moduleId} » ne figure plus dans le catalogue de la société —`
            + ' rechargez le catalogue, ou choisissez un module de la liste.',
        );
      }
    }
    if (moduleMentionEl) {
      const aucunChoix = !ctx.areas.some((z) => z.moduleId);
      moduleMentionEl.textContent = aucunChoix
        ? `${MODULE_PAR_DEFAUT_ATELIER.libelle} — ${
          catalogueAtelier.choisissables.length
            ? 'aucun module du catalogue n’est posé sur ce site.'
            : catalogueAtelier.motifListeVide
              ?? 'aucun module de la société n’est choisissable aujourd’hui.'
        }`
        : synthese?.mention ?? '';
    }
  }

  /**
   * CALX109/CALX110 — pose un modèle sur le pan ACTIF (chaîne vide = retour au module par
   * défaut de l'atelier, NOMMÉ). Un modèle grisé, inconnu, ou dont la fiche n'a pas de cotes
   * est REFUSÉ en nommant le champ fautif : RIEN n'est écrit sur le pan, et le pavage ne
   * bouge pas. Un choix accepté re-pave immédiatement (`deps.recalc`) — c'est tout l'intérêt
   * de choisir un module : ses VRAIES cotes changent le nombre de rangées.
   */
  function choisirModuleDuPanActif(moduleId: string | null | undefined): boolean {
    const a = ctx.activeArea();
    if (!a) return false;
    const id = typeof moduleId === 'string' ? moduleId.trim() : '';
    if (!id) {
      ctx.pushWorkshopHistory?.(); // CAL100 — annulable comme le reste de l'atelier
      delete a.moduleId;
      direRefusModule(null);
      deps.recalc?.();
      renderAreasPanel();
      deps.setStatus?.(`${nomDuPanActif()} : ${MODULE_PAR_DEFAUT_ATELIER.libelle}.`);
      return true;
    }
    const grise = catalogueAtelier.grises.find((g) => g.module.id === id);
    if (grise) {
      direRefusModule(`${nomDuPanActif()} : « ${grise.module.libelle} » — ${motifGrise(grise)}`);
      syncModulePicker();
      return false;
    }
    const module = resoudreModuleDuPan(catalogueAtelier.choisissables, id);
    if (estRefus(module)) {
      direRefusModule(`${nomDuPanActif()} : ${module.message}`);
      syncModulePicker();
      return false;
    }
    const cotes = cotesDeModule(module);
    if (estRefus(cotes)) {
      direRefusModule(`${nomDuPanActif()} : ${cotes.message}`);
      syncModulePicker();
      return false;
    }
    ctx.pushWorkshopHistory?.(); // CAL100 — annulable comme le reste de l'atelier
    a.moduleId = module.id;
    direRefusModule(null);
    deps.recalc?.(); // le pavage repart avec les VRAIES cotes de ce module
    renderAreasPanel();
    deps.setStatus?.(
      `${nomDuPanActif()} : module « ${module.libelle} » — le calepinage est repavé à ses cotes.`,
    );
    return true;
  }

  moduleSelectEl?.addEventListener('change', () => {
    choisirModuleDuPanActif(moduleSelectEl.value);
  });
  syncModulePicker(); // état initial : le module par défaut est NOMMÉ, jamais muet

  /** CAL59 — assigne le bâtiment d'une zone (chaîne vide = retour au bâtiment unique). */
  function setAreaBuilding(id: string, buildingId: string) {
    const a = ctx.areas.find((x) => x.id === id);
    if (!a) return;
    const trimmed = buildingId.trim();
    a.buildingId = trimmed ? trimmed : undefined;
    renderAreasPanel();
  }

  return {
    liveActiveResult,
    snapshotActiveAreaResult,
    snapshotActiveAreaGeometry,
    syncAddAreaButton,
    renderAreasPanel,
    setAreaBuilding,
    pivoterPanActif,
    redimensionnerPanActif,
    dupliquerPanActif,
    choisirModuleDuPanActif, // CALX109/CALX110 câblage
  };
}

// ————————————————————————————————————————————————————————————————————————
// CAL69 — ZONES INTERDITES / RÉSERVÉES / PRÉFÉRÉES TRACÉES DANS L'ATELIER
//
// L'atelier ne proposait que « + Ajouter une zone » au sens PAN DE TOIT : une
// servitude ou une bande coupe-feu tracée par le dessinateur ne changeait RIEN au
// compte publié. Ce bloc porte la zone d'EXCLUSION au sens CAL68, écrivant EXACTEMENT
// le contrat `exclusionZones` du document v2 (`contract_samples/zones.json`,
// `roof_layout_v2.schema.json` `$defs/exclusionZone`) : `id`, `label`, `nature`,
// `vertices` [[lng, lat], …], `setbackM`, `heightM`.
//
// LES DEUX GARANTIES DE CAL68, TENUES CÔTÉ ÉCRAN :
//  - INTERDITE et RESERVEE retirent leur surface du posable ⇒ le compte de modules
//    bouge IMMÉDIATEMENT (leurs anneaux rejoignent les obstructions du pavage) ;
//  - PREFEREE ne change JAMAIS un compte (bonus doux de départage côté moteur) ⇒
//    elle ne rejoint AUCUNE obstruction.
// ENVELOPPE existe dans le vocabulaire du moteur mais ne se trace pas ici : c'est le
// contour lui-même.
//
// GÉOMÉTRIE PURE : aucun Three, aucun DOM, aucune carte — testable seule.
// ————————————————————————————————————————————————————————————————————————

/** Natures traçables dans l'atelier (sous-ensemble de `core.calepinage.types.NatureZone` :
 *  ENVELOPPE est le contour, il ne se dessine pas comme une zone). */
export type ExclusionNature = 'INTERDITE' | 'RESERVEE' | 'PREFEREE';

/** CALX401 — les usages qu'une zone peut porter EN PLUS de sa nature. Un seul aujourd'hui. */
export type UsageZone = 'circulation';

/** CALX401 — l'usage « allée de circulation », tel que le contrat le nomme. */
export const USAGE_CIRCULATION: UsageZone = 'circulation';

export const EXCLUSION_NATURES: readonly { id: ExclusionNature; label: string; note: string }[] = [
  { id: 'INTERDITE', label: 'Interdite', note: 'retirée du posable — le compte baisse' },
  { id: 'RESERVEE', label: 'Réservée', note: 'retirée du posable, chiffrée à part' },
  { id: 'PREFEREE', label: 'Préférée', note: 'ne change jamais le compte' },
];

/** Code couleur DISTINCT de celui des obstacles (`#ff6b6b`) : une zone n'est pas un
 *  obstacle physique, on ne doit pas les confondre à l'œil. */
export const EXCLUSION_COLORS: Record<ExclusionNature, string> = {
  INTERDITE: '#8b5cf6',
  RESERVEE: '#38bdf8',
  PREFEREE: '#22c55e',
};

export function exclusionColor(nature: ExclusionNature): string {
  return EXCLUSION_COLORS[nature] ?? EXCLUSION_COLORS.INTERDITE;
}

/** Une zone d'exclusion du document d'atelier — MÊMES noms de clés que le contrat. */
export interface ExclusionZone {
  id: string;
  label?: string;
  nature: ExclusionNature;
  /** Contour [[lng, lat], …], même repère que `zones[].vertices` (les pans). */
  vertices: LngLat[];
  /** Retrait SAISI (m) autour de la zone. Jamais deviné : 0 tant que rien n'est saisi. */
  setbackM: number;
  /** Hauteur (m). `null`/absente = non renseignée — jamais un repli. */
  heightM?: number | null;
  /** CALX401/CALX403 — ce à quoi la zone SERT, quand ce n'est pas seulement sa nature.
   *  `circulation` = ALLÉE tracée sur le toit. Absent = zone d'exclusion ordinaire. */
  usage?: UsageZone;
  /** CALX401 — la POLYLIGNE tracée (≥ 2 points). Elle garde le GESTE ; c'est `vertices`
   *  qui fait foi pour la géométrie, le couloir y ayant été calculé depuis `axe` et
   *  `largeurM` au moment du tracé. */
  axe?: LngLat[];
  /** CALX401 — largeur SAISIE (m) du passage. Aucune largeur n'est livrée par le dépôt. */
  largeurM?: number;
}

/** Retrait PLANCHER/PLAFOND (m) — mêmes ordres de grandeur que les obstacles. */
export const ZONE_MAX_SETBACK_M = 10;
export const ZONE_MAX_HEIGHT_M = 60;

const ZONE_DEG2RAD = Math.PI / 180;
const ZONE_WGS84_RADIUS = 6378137;
const ZONE_DEG2M = ZONE_DEG2RAD * ZONE_WGS84_RADIUS;

function clampNum(v: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, v));
}

/** Zone rectangulaire née d'un glissé (deux coins), retrait 0 et hauteur non renseignée :
 *  RIEN n'est inventé tant que l'utilisateur n'a pas saisi. */
export function exclusionZoneFromDrag(id: string, nature: ExclusionNature, a: LngLat, b: LngLat): ExclusionZone {
  return {
    id,
    nature,
    vertices: [a, [b[0], a[1]], b, [a[0], b[1]]],
    setbackM: 0,
  };
}

export function withZoneNature(z: ExclusionZone, nature: ExclusionNature): ExclusionZone {
  return { ...z, nature };
}

export function withZoneSetback(z: ExclusionZone, setbackM: number | null | undefined): ExclusionZone {
  if (setbackM == null || !Number.isFinite(setbackM) || setbackM <= 0) return { ...z, setbackM: 0 };
  return { ...z, setbackM: clampNum(setbackM, 0, ZONE_MAX_SETBACK_M) };
}

export function withZoneHeight(z: ExclusionZone, heightM: number | null | undefined): ExclusionZone {
  if (heightM == null || !Number.isFinite(heightM) || heightM <= 0) {
    const { heightM: _drop, ...rest } = z;
    return rest;
  }
  return { ...z, heightM: clampNum(heightM, 0, ZONE_MAX_HEIGHT_M) };
}

export function withZoneLabel(z: ExclusionZone, label: string | null | undefined): ExclusionZone {
  const v = (label ?? '').trim();
  if (!v) {
    const { label: _drop, ...rest } = z;
    return rest;
  }
  return { ...z, label: v };
}

/**
 * Anneau AFFICHÉ/OPPOSÉ AU PAVAGE : le contour saisi, DILATÉ du retrait saisi (le
 * retrait d'une zone dilate son emprise, exactement comme `sommets_decales` côté
 * moteur). Retrait 0 ⇒ le contour tel quel. Moins de 3 sommets ⇒ rien à dessiner.
 */
export function exclusionZoneRing(z: ExclusionZone): LngLat[] | null {
  if (!z.vertices || z.vertices.length < 3) return null;
  if (!(z.setbackM > 0)) return z.vertices.map((v) => [v[0], v[1]] as LngLat);
  let sumLng = 0;
  let sumLat = 0;
  for (const [lng, lat] of z.vertices) {
    sumLng += lng;
    sumLat += lat;
  }
  const cLng = sumLng / z.vertices.length;
  const cLat = sumLat / z.vertices.length;
  const cosLat = Math.max(1e-6, Math.cos(cLat * ZONE_DEG2RAD));
  return z.vertices.map(([lng, lat]) => {
    const dx = (lng - cLng) * ZONE_DEG2M * cosLat;
    const dy = (lat - cLat) * ZONE_DEG2M;
    const d = Math.hypot(dx, dy);
    if (d < 1e-9) return [lng, lat] as LngLat;
    const k = (d + z.setbackM) / d;
    return [cLng + (dx * k) / (ZONE_DEG2M * cosLat), cLat + (dy * k) / ZONE_DEG2M] as LngLat;
  });
}

/** Zones qui RETIRENT de la surface posable : INTERDITE et RESERVEE. PREFEREE jamais. */
export function blockingExclusionZones(list: readonly ExclusionZone[] | null | undefined): ExclusionZone[] {
  return (list ?? []).filter((z) => z.nature === 'INTERDITE' || z.nature === 'RESERVEE');
}

/** Anneaux d'obstruction apportés par les zones — à concaténer aux obstacles du pavage.
 *  Une PRÉFÉRÉE n'en produit AUCUN : c'est ce qui garantit que le compte ne bouge pas. */
export function exclusionObstructionRings(list: readonly ExclusionZone[] | null | undefined): LngLat[][] {
  const out: LngLat[][] = [];
  for (const z of blockingExclusionZones(list)) {
    const ring = exclusionZoneRing(z);
    if (ring) out.push(ring);
  }
  return out;
}

/** Sérialisation vers le document v2 (`exclusionZones`) : clés du contrat, rien de plus,
 *  et aucune zone invalide (< 3 sommets) n'est écrite. */
export function serializeExclusionZones(
  list: readonly ExclusionZone[] | null | undefined,
): Array<ZoneSerialisee> {
  const out: Array<ZoneSerialisee> = [];
  for (const z of list ?? []) {
    if (!z || !Array.isArray(z.vertices) || z.vertices.length < 3) continue;
    if (z.nature !== 'INTERDITE' && z.nature !== 'RESERVEE' && z.nature !== 'PREFEREE') continue;
    out.push({
      id: String(z.id),
      ...(z.label ? { label: z.label } : {}),
      nature: z.nature,
      vertices: z.vertices.map((v) => [v[0], v[1]] as LngLat),
      setbackM: Number.isFinite(z.setbackM) && z.setbackM > 0 ? z.setbackM : 0,
      heightM: Number.isFinite(z.heightM as number) && (z.heightM as number) > 0 ? (z.heightM as number) : null,
      // CALX401/CALX403 — l'allée voyage AVEC son geste et sa largeur SAISIE, ou pas du
      // tout : les trois clés sont indissociables (le contrat exige `axe` + `largeurM`
      // dès que `usage` vaut `circulation`), donc on n'en émet jamais une partie.
      ...champsAlleeCirculation(z),
    });
  }
  return out;
}

/** Forme SÉRIALISÉE d'une zone d'exclusion — les clés du contrat, rien de plus. */
export interface ZoneSerialisee {
  id: string;
  label?: string;
  nature: ExclusionNature;
  vertices: LngLat[];
  setbackM: number;
  heightM: number | null;
  usage?: UsageZone;
  axe?: LngLat[];
  largeurM?: number;
}

/** Relecture d'un document : tolérante aux formes bancales, ne fabrique jamais de zone. */
export function deserializeExclusionZones(json: unknown): ExclusionZone[] {
  if (!Array.isArray(json)) return [];
  const out: ExclusionZone[] = [];
  for (const raw of json) {
    const z = raw as Partial<ExclusionZone> | null;
    if (!z || typeof z.id !== 'string') continue;
    if (z.nature !== 'INTERDITE' && z.nature !== 'RESERVEE' && z.nature !== 'PREFEREE') continue;
    const verts = Array.isArray(z.vertices)
      ? z.vertices
          .filter((v): v is LngLat => Array.isArray(v) && v.length === 2 && Number.isFinite(v[0]) && Number.isFinite(v[1]))
          .map((v) => [v[0], v[1]] as LngLat)
      : [];
    if (verts.length < 3) continue;
    let zone: ExclusionZone = { id: z.id, nature: z.nature, vertices: verts, setbackM: 0 };
    zone = withZoneSetback(zone, typeof z.setbackM === 'number' ? z.setbackM : null);
    zone = withZoneHeight(zone, typeof z.heightM === 'number' ? z.heightM : null);
    zone = withZoneLabel(zone, typeof z.label === 'string' ? z.label : null);
    // CALX401/CALX403 — l'allée se relit telle qu'elle a été écrite (geste + largeur
    // SAISIE). Une allée amputée de son axe ou de sa largeur n'est plus une allée : elle
    // se relit alors comme la zone d'exclusion ordinaire qu'elle reste, jamais complétée.
    zone = { ...zone, ...champsAlleeCirculation(raw) };
    out.push(zone);
  }
  return out;
}

// ————————————————————————————————————————————————————————————————————————
// CALX403 — ALLÉE DE CIRCULATION TRACÉE DANS L'ATELIER
//
// L'atelier ne savait dessiner qu'un obstacle rectangulaire au glissé et des zones
// polygonales : aucun outil ne traçait un COULOIR par sa polyligne et sa largeur, et rien
// ne signalait un module posé en travers d'un passage. Le panneau d'allées existant
// (CAL70) ne règle que la largeur UNIFORME entre rangées — un retrait entre rangées et un
// passage de pompier ne sont pas la même pièce. Parité Aurora (« fire pathways » : les
// modules chevauchants passent en jaune, et un glissé conserve l'orientation et la largeur).
//
// ZÉRO LARGEUR INVENTÉE (D-CALX 7, CALX402) : le dépôt ne porte AUCUNE largeur de
// référence. Sans largeur saisie pour le pays du site, l'allée est OMISE et le motif NOMME
// le pays ET le réglage manquant — jamais une largeur supposée.
//
// GÉOMÉTRIE PURE : aucun Three, aucun DOM, aucune carte.
// ————————————————————————————————————————————————————————————————————————

/** Les clés d'allée d'une zone, à ÉMETTRE ou à RELIRE — les trois ensemble, ou aucune. */
function champsAlleeCirculation(
  brut: unknown,
): { usage?: UsageZone; axe?: LngLat[]; largeurM?: number } {
  const z = (brut ?? {}) as Partial<ExclusionZone>;
  if (z.usage !== USAGE_CIRCULATION) return {};
  const axe = Array.isArray(z.axe)
    ? z.axe
        .filter((p): p is LngLat => Array.isArray(p) && p.length === 2 && Number.isFinite(p[0]) && Number.isFinite(p[1]))
        .map((p) => [p[0], p[1]] as LngLat)
    : [];
  const largeur = z.largeurM;
  if (axe.length < 2) return {};
  if (typeof largeur !== 'number' || !Number.isFinite(largeur) || largeur <= 0) return {};
  return { usage: USAGE_CIRCULATION, axe, largeurM: largeur };
}

/**
 * CALX403 — la largeur d'allée de circulation SAISIE par la société pour un pays, lue dans
 * la section `degagements` des réglages (`allees_circulation`). C'est le JUMEAU côté écran
 * de `services/degagements.py::largeur_allee_circulation` (CALX402) : mêmes clés, même
 * règle, et surtout le même refus — pays non saisi ⇒ `largeurM: null` et un motif qui NOMME
 * le réglage manquant. AUCUN défaut n'est fabriqué ici.
 */
export function largeurAlleeDepuisReglages(
  sectionDegagements: unknown,
  pays: string | null | undefined,
): { largeurM: number | null; motif: string } {
  const code = String(pays ?? '').trim().toLowerCase();
  const reglage = `degagements.allees_circulation.${code || '?'}`;
  if (!code) {
    return {
      largeurM: null,
      motif: `Allée de circulation : aucun pays n’est réglé pour ce site — réglage manquant : ${reglage}.`,
    };
  }
  const section = (sectionDegagements ?? {}) as Record<string, unknown>;
  const entrees = Array.isArray(section.allees_circulation) ? (section.allees_circulation as unknown[]) : [];
  for (const brut of entrees) {
    if (!brut || typeof brut !== 'object' || Array.isArray(brut)) continue;
    const e = brut as Record<string, unknown>;
    if (String(e.pays ?? '').trim().toLowerCase() !== code) continue;
    const largeur = e.largeur_m;
    if (typeof largeur !== 'number' || !Number.isFinite(largeur) || largeur <= 0) break;
    const source = String(e.source ?? '').trim();
    const reference = String(e.reference ?? '').trim();
    const citation = [source || 'source non renseignée', reference].filter(Boolean).join(', ');
    return {
      largeurM: largeur,
      motif: `Allée de circulation (${code}) : ${largeur} m (réglage de votre société — ${citation}).`,
    };
  }
  return {
    largeurM: null,
    motif:
      `Allée de circulation (${code}) : aucune largeur n’est saisie pour ce pays — ` +
      `réglage manquant : ${reglage}. L’allée n’est pas tracée tant qu’elle n’est pas saisie.`,
  };
}

/** Verdict d'un tracé d'allée — un refus NOMME toujours sa raison. */
export type VerdictAllee = { ok: true; zone: ExclusionZone } | { ok: false; motif: string };

/** CALX403 — la largeur saisie est-elle exploitable ? `null` = oui, sinon le motif. */
export function motifLargeurAllee(largeurM: number | null | undefined, pays?: string | null): string | null {
  if (largeurM == null || !Number.isFinite(largeurM) || largeurM <= 0) {
    const code = String(pays ?? '').trim().toLowerCase();
    const reglage = `degagements.allees_circulation.${code || '?'}`;
    return (
      'Allée non tracée : saisissez sa largeur en mètres. Aucune largeur n’est supposée — ' +
      `réglage manquant : ${reglage}.`
    );
  }
  return null;
}

/**
 * CALX403 — le COULOIR (contour fermé) d'une polyligne ÉLARGIE de sa largeur saisie : on
 * décale chaque point de la moitié de la largeur de part et d'autre, puis on referme
 * (côté gauche + côté droit parcouru à l'envers). Les extrémités ne sont PAS prolongées :
 * un couloir de 1 m de large sur 10 m de long fait 10 m², pas un mètre de plus.
 *
 * Aux coudes, le décalage suit la BISSECTRICE (longueur de l'onglet), pour que la largeur
 * MESURÉE en travers du passage reste celle qui a été saisie. Un virage en épingle verrait
 * cet onglet partir à l'infini : il est borné (convention de DESSIN, `ONGLET_MIN`), ce qui
 * ne change ni la largeur saisie ni le geste enregistré.
 */
export function couloirDepuisAxe(axe: readonly LngLat[], largeurM: number): LngLat[] | null {
  const pts = (axe ?? []).filter(
    (p): p is LngLat => Array.isArray(p) && p.length === 2 && Number.isFinite(p[0]) && Number.isFinite(p[1]),
  );
  if (pts.length < 2 || !Number.isFinite(largeurM) || largeurM <= 0) return null;
  const cosLat = Math.max(1e-6, Math.cos(pts[0][1] * ZONE_DEG2RAD));
  const versEnu = ([lng, lat]: LngLat): [number, number] => [
    (lng - pts[0][0]) * ZONE_DEG2M * cosLat,
    (lat - pts[0][1]) * ZONE_DEG2M,
  ];
  const versLngLat = ([x, y]: [number, number]): LngLat => [
    pts[0][0] + x / (ZONE_DEG2M * cosLat),
    pts[0][1] + y / ZONE_DEG2M,
  ];
  const enu = pts.map(versEnu);
  // Normale unitaire (à gauche) de chaque segment ; un segment de longueur nulle n'en a pas.
  const normales: Array<[number, number] | null> = [];
  for (let i = 0; i < enu.length - 1; i++) {
    const dx = enu[i + 1][0] - enu[i][0];
    const dy = enu[i + 1][1] - enu[i][1];
    const len = Math.hypot(dx, dy);
    normales.push(len < 1e-9 ? null : [-dy / len, dx / len]);
  }
  const valides = normales.filter((n): n is [number, number] => n != null);
  if (!valides.length) return null;
  const demi = largeurM / 2;
  const ONGLET_MIN = 0.4; // convention de dessin : borne de l'onglet en épingle
  const gauche: Array<[number, number]> = [];
  const droite: Array<[number, number]> = [];
  for (let i = 0; i < enu.length; i++) {
    const avant = i > 0 ? normales[i - 1] : null;
    const apres = i < normales.length ? normales[i] : null;
    let dep: [number, number];
    if (avant && apres) {
      const mx = avant[0] + apres[0];
      const my = avant[1] + apres[1];
      const m = Math.max(ONGLET_MIN, Math.hypot(mx, my));
      dep = [(mx * largeurM) / (m * m), (my * largeurM) / (m * m)];
    } else {
      const n = (apres ?? avant) as [number, number];
      dep = [n[0] * demi, n[1] * demi];
    }
    gauche.push([enu[i][0] + dep[0], enu[i][1] + dep[1]]);
    droite.push([enu[i][0] - dep[0], enu[i][1] - dep[1]]);
  }
  return [...gauche, ...droite.reverse()].map(versLngLat);
}

/**
 * CALX403 — construit l'allée de circulation depuis le geste tracé et la largeur SAISIE.
 * Elle est de nature INTERDITE : sa surface est retirée du posable comme n'importe quelle
 * zone interdite (`exclusionObstructionRings` la reprend sans rien changer). Refus NOMMÉ
 * quand l'axe est trop court ou la largeur non saisie — jamais une allée sans largeur.
 */
export function alleeCirculation(
  id: string,
  axe: readonly LngLat[],
  largeurM: number | null | undefined,
  pays?: string | null,
): VerdictAllee {
  const pts = (axe ?? []).filter(
    (p): p is LngLat => Array.isArray(p) && p.length === 2 && Number.isFinite(p[0]) && Number.isFinite(p[1]),
  );
  if (pts.length < 2) {
    return { ok: false, motif: 'Allée non tracée : il faut au moins deux points — un passage à un point ne mène nulle part.' };
  }
  const motif = motifLargeurAllee(largeurM, pays);
  if (motif) return { ok: false, motif };
  const vertices = couloirDepuisAxe(pts, largeurM as number);
  if (!vertices || vertices.length < 3) {
    return { ok: false, motif: 'Allée non tracée : les points saisis sont confondus, aucun couloir n’en sort.' };
  }
  return {
    ok: true,
    zone: {
      id,
      nature: 'INTERDITE',
      vertices,
      setbackM: 0,
      usage: USAGE_CIRCULATION,
      axe: pts.map((p) => [p[0], p[1]] as LngLat),
      largeurM: largeurM as number,
    },
  };
}

/** CALX403 — l'allée déplacée d'un delta lng/lat : l'axe ET le couloir suivent le même
 *  mouvement, et `largeurM` est recopiée TELLE QUELLE (le glissé ne re-dérive aucune cote,
 *  donc la largeur est conservée au millimètre). Une zone qui n'est pas une allée est
 *  renvoyée inchangée. */
export function deplacerAllee(z: ExclusionZone, dLng: number, dLat: number): ExclusionZone {
  if (z?.usage !== USAGE_CIRCULATION || !Array.isArray(z.axe)) return z;
  return {
    ...z,
    vertices: (z.vertices ?? []).map(([lng, lat]) => [lng + dLng, lat + dLat] as LngLat),
    axe: z.axe.map(([lng, lat]) => [lng + dLng, lat + dLat] as LngLat),
    largeurM: z.largeurM,
  };
}

/** CALX403 — l'aire (m²) réellement retirée par une allée : celle de son couloir. */
export function aireAlleeM2(z: ExclusionZone): number {
  const ring = exclusionZoneRing(z);
  return ring ? geodesicAreaM2(ring) : 0;
}

/** CALX403 — un module POSÉ, tel que l'atelier le connaît : son repère et son emprise au
 *  sol en mètres ENU autour de l'origine de la scène. */
export interface ModulePose {
  repere: string;
  empriseM: Array<[number, number]>;
}

/**
 * CALX403 — l'emprise au sol d'un module posé, en ENU, depuis ce que le pavage publie :
 * son centre (`cx`, `cy`), l'azimut du pavage, la largeur de rangée et la profondeur AU SOL
 * (`footprintPerPanelM2 / rowWidthM`). Mêmes vecteurs de base que le pavage
 * (`estimatorBrainV2` : `s = [sin az, cos az]` empile les rangées, `u = [-cos az, sin az]`
 * porte la rangée) : aucune cote n'est inventée, toutes sont lues sur le plan.
 */
export function empriseModuleENU(
  centre: { cx: number; cy: number },
  azimutDeg: number,
  largeurRangeeM: number,
  profondeurAuSolM: number,
): Array<[number, number]> {
  const az = azimutDeg * ZONE_DEG2RAD;
  const s: [number, number] = [Math.sin(az), Math.cos(az)];
  const u: [number, number] = [-s[1], s[0]];
  const du = largeurRangeeM / 2;
  const dv = profondeurAuSolM / 2;
  return [
    [-du, -dv],
    [du, -dv],
    [du, dv],
    [-du, dv],
  ].map(([a, b]) => [centre.cx + a * u[0] + b * s[0], centre.cy + a * u[1] + b * s[1]] as [number, number]);
}

/** Deux segments se croisent-ils ? (orientations opposées de part et d'autre). */
function segmentsSeCroisent(
  p1: [number, number],
  p2: [number, number],
  p3: [number, number],
  p4: [number, number],
): boolean {
  const d = (a: [number, number], b: [number, number], c: [number, number]) =>
    (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]);
  const d1 = d(p3, p4, p1);
  const d2 = d(p3, p4, p2);
  const d3 = d(p1, p2, p3);
  const d4 = d(p1, p2, p4);
  return ((d1 > 0) !== (d2 > 0)) && ((d3 > 0) !== (d4 > 0));
}

/**
 * CALX403 — les REPÈRES des modules qui chevauchent l'allée. Un module est chevauchant si
 * un de ses coins est dans le couloir, si un sommet du couloir est dans son emprise, ou si
 * leurs bords se croisent (cas du passage étroit qui TRAVERSE une rangée : ni coin ni
 * sommet ne tombe dans l'autre, et pourtant ils se chevauchent).
 *
 * CETTE FONCTION NE SUPPRIME RIEN : elle COMPTE. Parité Aurora — un module posé en travers
 * d'un passage est signalé, jamais effacé dans le dos du dessinateur.
 */
export function modulesSurAllee(
  modules: readonly ModulePose[],
  allee: ExclusionZone,
  origine: LngLat,
): string[] {
  if (allee?.usage !== USAGE_CIRCULATION) return [];
  const ring = exclusionZoneRing(allee);
  if (!ring || ring.length < 3) return [];
  const cosLat = Math.max(1e-6, Math.cos(origine[1] * ZONE_DEG2RAD));
  const couloir = ring.map(
    ([lng, lat]) => [(lng - origine[0]) * ZONE_DEG2M * cosLat, (lat - origine[1]) * ZONE_DEG2M] as [number, number],
  );
  const touche = (emprise: Array<[number, number]>): boolean => {
    if (emprise.length < 3) return false;
    if (emprise.some((c) => pointInPolygon(c, couloir))) return true;
    if (couloir.some((c) => pointInPolygon(c, emprise))) return true;
    for (let i = 0; i < emprise.length; i++) {
      const a = emprise[i];
      const b = emprise[(i + 1) % emprise.length];
      for (let j = 0; j < couloir.length; j++) {
        if (segmentsSeCroisent(a, b, couloir[j], couloir[(j + 1) % couloir.length])) return true;
      }
    }
    return false;
  };
  return (modules ?? []).filter((m) => touche(m.empriseM ?? [])).map((m) => m.repere);
}
