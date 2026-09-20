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

export interface Zones {
  liveActiveResult: () => AreaResult | null;
  snapshotActiveAreaResult: () => void;
  snapshotActiveAreaGeometry: () => void;
  syncAddAreaButton: () => void;
  renderAreasPanel: () => void;
  /** CAL59 — assigne (ou efface, chaîne vide) le bâtiment d'une zone, puis re-rend le
   *  panneau. N'affecte ni le résultat ni la géométrie de la zone. */
  setAreaBuilding: (id: string, buildingId: string) => void;
}

/** CAL84 — libellé d'un bâtiment (repli « Bâtiment sans id » pour un groupe sans
 *  `buildingId` mélangé à des zones qui en portent un — cas limite, ne devrait pas
 *  arriver en pratique une fois CAL59 câblé, mais ne doit jamais planter l'affichage). */
function buildingLabel(buildingId: string | null): string {
  return buildingId ? buildingId : 'Bâtiment sans id';
}

export function createZones(ctx: Ctx): Zones {
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
  };
}
