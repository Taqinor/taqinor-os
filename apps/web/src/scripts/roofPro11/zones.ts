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
import { type LngLat } from '../../lib/roof';
import { type Obstacle } from '../../lib/obstacles';
import {
  centroideAnneau,
  dimensionsRectangleM,
  pivoterAnneau,
  pivoterPoint,
  redimensionnerRectangle,
} from './snap';
import { computePanStats, hasMultipleBuildings, type PanStat } from './panStats';

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
    const stats = computePanStats(areas, (a) => (a.id === activeAreaId ? liveActive : a.result));
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
): Array<{ id: string; label?: string; nature: ExclusionNature; vertices: LngLat[]; setbackM: number; heightM: number | null }> {
  const out: Array<{ id: string; label?: string; nature: ExclusionNature; vertices: LngLat[]; setbackM: number; heightM: number | null }> = [];
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
    });
  }
  return out;
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
    out.push(zone);
  }
  return out;
}
