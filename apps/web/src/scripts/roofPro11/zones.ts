/**
 * « Plusieurs zones » : instantané du résultat/géométrie de la zone active +
 * rendu du panneau de total agrégé. Extrait de roof-tool-pro11.ts (split
 * modulaire 2026-06-20) — comportement INCHANGÉ.
 *
 * Le RENDU 3D des autres zones (`appendOtherZones`, couplé à `buildZoneMeshes`)
 * reste dans roof-tool-pro11.ts tant que la scène n'est pas extraite.
 */
import { aggregateAreas, areaLabel, type AreaResult } from '../../lib/roofAreas';
import { fmt, fmtMad, esc } from './dom';
import { type Ctx } from './context';

export interface Zones {
  liveActiveResult: () => AreaResult | null;
  snapshotActiveAreaResult: () => void;
  snapshotActiveAreaGeometry: () => void;
  syncAddAreaButton: () => void;
  renderAreasPanel: () => void;
}

export function createZones(ctx: Ctx): Zones {
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
    const total = aggregateAreas(results);
    if (areasTotalPanelsEl) areasTotalPanelsEl.textContent = `${fmt(total.panels)} × 720 W`;
    if (areasTotalKwcEl) areasTotalKwcEl.textContent = `${total.kwc.toLocaleString('fr-FR', { maximumFractionDigits: 1 })} kWc`;
    if (areasTotalProdEl) areasTotalProdEl.textContent = total.annualKwh > 0 ? `${fmt(Math.round(total.annualKwh))} kWh/an` : '—';
    if (areasTotalSavingsEl) areasTotalSavingsEl.textContent = total.savingsHigh > 0 ? `${fmtMad(total.savingsLow)} – ${fmtMad(total.savingsHigh)}/an` : '—';
    if (!areasListEl) return;
    areasListEl.innerHTML = areas
      .map((a, i) => {
        const r = a.id === activeAreaId ? liveActive : a.result;
        const active = a.id === activeAreaId;
        const panels = r ? fmt(r.panels) : '—';
        const kwc = r ? `${r.kwc.toLocaleString('fr-FR', { maximumFractionDigits: 1 })} kWc` : 'à tracer';
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
        return `<li class="flex flex-wrap items-center gap-x-3 gap-y-1 border ${rowClass} p-3 text-sm" data-area-row="${a.id}">
          <span class="font-semibold text-white">${esc(areaLabel(i))}</span>
          <span class="text-xs text-lune-faint">${panels} panneaux · ${kwc}</span>
          <span class="ml-auto flex items-center gap-2">${viewBtn}${delBtn}</span>
        </li>`;
      })
      .join('');
  }

  return { liveActiveResult, snapshotActiveAreaResult, snapshotActiveAreaGeometry, syncAddAreaButton, renderAreasPanel };
}
