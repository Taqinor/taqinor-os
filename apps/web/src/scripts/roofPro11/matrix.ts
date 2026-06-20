/**
 * V6 — MATRICE de comparaison (toit plat) : balayage dense affiché, triable et
 * filtrable, optimum réel épinglé en tête + badgé « Recommandé ». Extrait de
 * roof-tool-pro11.ts (split modulaire 2026-06-20) — comportement INCHANGÉ.
 *
 * Le balayage pur (`fineGridMatrixV6`) reste dans lib/estimatorBrainV6 ; ce
 * module ne fait que l'afficher et router les clics de ligne vers le rendu
 * unifié de configuration (injecté : `renderConfig`).
 */
import { packConfig } from '../../lib/estimatorBrainV2';
import {
  fineGridMatrixV6,
  matrixGroupKey,
  sortMatrix,
  type MatrixEvalV6,
  type MatrixSortKey,
} from '../../lib/estimatorBrainV6';
import { PERIMETER_SETBACK_M } from '../../lib/roofPro2';
import { type LngLat } from '../../lib/roof';
import { $, fmt, fmtMad } from './dom';
import { type Ctx } from './context';
import { type RenderConfigOpts } from './types';

/** Dépendances injectées (rendu de config + facture + obstacles). */
export interface MatrixDeps {
  /** Rendu unifié d'une configuration toit plat (carte + 3D + contrôles). */
  renderConfig: (o: RenderConfigOpts) => void;
  /** Facture mensuelle saisie (MAD). */
  monthlyBill: () => number;
  /** Anneaux lng/lat des obstacles (zones d'exclusion). */
  obstructionRings: () => LngLat[][];
}

export interface Matrix {
  paintComparison: () => void;
  renderMatrixRow: (r: MatrixEvalV6) => void;
  highlightRow: (id: string | null) => void;
  recomputeMatrix: () => void;
  setMatrixSort: (key: MatrixSortKey) => void;
}

export function createMatrix(ctx: Ctx, deps: MatrixDeps): Matrix {
  const { renderConfig, monthlyBill, obstructionRings } = deps;

  /** Clé stable d'une ligne (famille|inclinaison|azimut|pose|marge) — sert d'id de
   *  ligne (réutilise le highlight existant) et de comparaison au gagnant. */
  function matrixRowKey(r: MatrixEvalV6): string {
    return `${r.family}|${r.tiltDeg}|${Math.round(r.azimuthDeg)}|${r.orientation}|${r.margin}`;
  }

  function isMatrixWinner(r: MatrixEvalV6): boolean {
    const w = ctx.matrixResult?.winner;
    return !!w && matrixRowKey(r) === matrixRowKey(w);
  }

  /** Lignes ordonnées selon le tri + filtre courants (vrai regroupement, lisible). */
  function matrixOrderedRows(): MatrixEvalV6[] {
    const matrixResult = ctx.matrixResult;
    if (!matrixResult) return [];
    const rows = ctx.matrixFilter === 'all' ? matrixResult.rows : matrixResult.rows.filter((r) => matrixGroupKey(r) === ctx.matrixFilter);
    return sortMatrix(rows, ctx.matrixSort.key, ctx.matrixSort.dir);
  }

  /** (Re)peuple le menu de filtre par orientation/pose à partir de la matrice. */
  function syncMatrixFilter() {
    const sel = $<HTMLSelectElement>('rp9-matrix-filter');
    const matrixResult = ctx.matrixResult;
    if (!sel || !matrixResult) return;
    const groups = [...new Set(matrixResult.rows.map(matrixGroupKey))].sort();
    const want = ['all', ...groups];
    const current = want.join('|');
    if (sel.dataset.built !== current) {
      sel.innerHTML =
        `<option value="all">Toutes les orientations (${matrixResult.rows.length} configs)</option>` +
        groups.map((g) => `<option value="${g}">${g}</option>`).join('');
      sel.dataset.built = current;
    }
    if (ctx.matrixFilter !== 'all' && !groups.includes(ctx.matrixFilter)) ctx.matrixFilter = 'all';
    sel.value = ctx.matrixFilter;
  }

  /** Reflète l'en-tête de tri actif (flèche + aria-sort sur la cellule) sur les
   *  colonnes triables. `data-rp9-sort` vit sur le bouton ; aria-sort sur son <th>. */
  function syncMatrixSortHeaders() {
    for (const btn of Array.from(document.querySelectorAll<HTMLElement>('[data-rp9-sort]'))) {
      const key = btn.dataset.rp9Sort as MatrixSortKey;
      const active = key === ctx.matrixSort.key;
      btn.dataset.active = active ? 'true' : 'false';
      const th = btn.closest('th');
      if (th) th.setAttribute('aria-sort', active ? (ctx.matrixSort.dir === 'desc' ? 'descending' : 'ascending') : 'none');
      const arrow = btn.querySelector('.rp9-sort-arrow');
      if (arrow) arrow.textContent = active ? (ctx.matrixSort.dir === 'desc' ? ' ↓' : ' ↑') : '';
    }
  }

  function paintComparison() {
    // W35 — la matrice plate ne doit JAMAIS repeindre le tableau en mode pente
    // (le comparatif pente est rendu par paintPitchedComparison).
    if (ctx.roofType !== 'flat' || !ctx.rec || !ctx.matrixResult) return;
    const matrixResult = ctx.matrixResult;
    const tbody = $('rp9-compare');
    const wrap = $('rp9-compare-wrap');
    if (!tbody) return;
    syncMatrixFilter();
    syncMatrixSortHeaders();
    const target = matrixResult.targetAnnualKwh;
    const winner = matrixResult.winner;
    // Optimum réel ÉPINGLÉ en tête, puis le reste de la matrice (triée/filtrée).
    const rest = matrixOrderedRows().filter((r) => !isMatrixWinner(r));
    const rows = [winner, ...rest];
    tbody.innerHTML = '';
    for (const r of rows) {
      const tr = document.createElement('tr');
      const key = matrixRowKey(r);
      tr.dataset.id = key;
      const win = isMatrixWinner(r);
      const cover = target > 0 ? Math.round(r.pctOfTarget) : 0;
      const badge = win ? ' <span style="color:var(--color-brass-300)">✓ Recommandé</span>' : '';
      tr.innerHTML =
        `<td>${r.label}${badge}</td>` +
        `<td class="num">${fmt(r.placedCount)}</td>` +
        `<td class="num">${r.kwc.toLocaleString('fr-FR', { maximumFractionDigits: 1 })}</td>` +
        `<td class="num">${fmt(Math.round(r.annualKwh))}</td>` +
        `<td class="num">${cover} %</td>` +
        `<td class="num">${fmtMad(r.savingsLow)} – ${fmtMad(r.savingsHigh)}</td>`;
      tr.addEventListener('click', () => renderMatrixRow(r));
      tbody.appendChild(tr);
    }
    if (wrap) wrap.hidden = false;
    highlightRow(isMatrixWinner(winner) ? matrixRowKey(winner) : null);
  }

  /** Rend EXACTEMENT cette ligne de la matrice en 3D (azimut span quelconque géré) :
   *  pavage à l'azimut/marge de la ligne, puis le rendu unifié toit plat. */
  function renderMatrixRow(r: MatrixEvalV6) {
    if (!ctx.closed || ctx.vertices.length < 3) return;
    ctx.useRecommended = false;
    const ring: LngLat[] = [...ctx.vertices];
    const setbackM = r.margin === 'keep' ? PERIMETER_SETBACK_M : 0;
    const pack = packConfig(ring, ctx.centroidLat, {
      family: r.family,
      tiltDeg: r.tiltDeg,
      azimuthDeg: r.azimuthDeg,
      obstructions: obstructionRings(),
      setbackM,
    });
    const grid = r.orientation === 'portrait' ? pack.portrait : pack.landscape;
    const matrixResult = ctx.matrixResult;
    renderConfig({
      pack,
      grid,
      family: r.family,
      tiltDeg: r.tiltDeg,
      azimuthDeg: pack.azimuthDeg,
      isReco: isMatrixWinner(r),
      title: `${r.label}${isMatrixWinner(r) ? '  ·  ✓ recommandé' : ''}`,
      why: isMatrixWinner(r)
        ? matrixResult?.optimumRow.reason ?? ''
        : 'Vous explorez une configuration de la matrice. La ligne « Recommandé » reste le meilleur compromis pour votre facture.',
      sourceLabel: matrixResult?.yieldSource === 'pvgis' ? '(production affinée via PVGIS au GPS exact)' : '(production estimée — table par latitude)',
      rowId: matrixRowKey(r),
    });
  }

  function highlightRow(id: string | null) {
    const tbody = $('rp9-compare');
    if (!tbody) return;
    for (const tr of Array.from(tbody.querySelectorAll('tr'))) {
      (tr as HTMLElement).dataset.active = (id != null && (tr as HTMLElement).dataset.id === id) ? 'true' : 'false';
    }
  }

  /** Recalcule la matrice (estimation instantanée) et la peint. Le balayage PVGIS au
   *  GPS exact suit en asynchrone (computeMatrixPvgis). */
  function recomputeMatrix() {
    if (!ctx.closed || ctx.vertices.length < 3 || ctx.roofType !== 'flat') return;
    const ring: LngLat[] = [...ctx.vertices];
    ctx.matrixResult = fineGridMatrixV6(ring, ctx.centroidLat, monthlyBill(), obstructionRings());
    paintComparison();
  }

  // Bascule de tri (clic sur en-tête) : même colonne → inverse le sens, sinon nouvelle
  // colonne en décroissant. Repeint sans re-balayer (la matrice est déjà calculée).
  function setMatrixSort(key: MatrixSortKey) {
    if (ctx.roofType !== 'flat') return; // le tri/filtre n'existent qu'en toit plat
    if (ctx.matrixSort.key === key) ctx.matrixSort = { key, dir: ctx.matrixSort.dir === 'desc' ? 'asc' : 'desc' };
    else ctx.matrixSort = { key, dir: 'desc' };
    paintComparison();
  }

  return { paintComparison, renderMatrixRow, highlightRow, recomputeMatrix, setMatrixSort };
}
