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
  CIBLES_OPTIMISATION,
  fineGridMatrixV6,
  libelleCible,
  matrixGroupKey,
  resoudreCibleOptimisation,
  sortMatrix,
  type MatrixEvalV6,
  type MatrixSortKey,
} from '../../lib/estimatorBrainV6';
import {
  choixOptimisationCourant,
  cibleOptimisationSaisie,
  poserCibleOptimisation,
} from './optimizer';
import { PERIMETER_SETBACK_M } from '../../lib/roofPro2';
import { type LngLat } from '../../lib/roof';
import { $, esc, fmt, fmtMad } from './dom';
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

  // W73 — MÊME clé de cache PVGIS que l'optimiseur (`v4Key`) : le tableau matrice et la
  // carte « reco » lisent le rendement spécifique au GPS exact dans le SEUL cache partagé
  // `ctx.v4YieldCache`, donc ils notent les configs sur la MÊME source. Tant que PVGIS
  // n'a rien renvoyé (cache vide) le yieldFn rend null → repli table « estimé » cohérent
  // des deux côtés.
  const v4Key = (tiltDeg: number, aspect: number): string => `${Math.round(tiltDeg)}|${Math.round(aspect * 10) / 10}`;
  const matrixYieldFn = (tiltDeg: number, aspect: number): number | null => {
    const v = ctx.v4YieldCache.get(v4Key(tiltDeg, aspect));
    return v == null ? null : v;
  };

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

  // ── CALX114 — la puce « objectif du classement », créée par le module ───────────
  /** Conteneur de la puce, créé en tête du bloc comparatif si la page ne le fournit
   *  pas (même patron que les contrôles d'obstacles/zones). */
  function cibleHost(): HTMLElement | null {
    const existant = $('rp9-cible');
    if (existant) return existant;
    const ancre = $('rp9-compare-wrap') ?? $('rp9-results');
    if (!ancre || typeof document.createElement !== 'function') return null;
    const host = document.createElement('div');
    host.id = 'rp9-cible';
    host.className = 'rp9-cible';
    ancre.insertBefore(host, ancre.firstChild);
    return host;
  }

  /** La phrase qui NOMME ce qui classe le balayage : celle du balayage lui-même dès
   *  qu'il a tourné (lui seul sait quelles mesures existent), sinon celle du choix
   *  saisi. Jamais un blanc : un classement muet est indiscernable d'un choix. */
  function motifCible(): string {
    return ctx.matrixResult?.cible.motif ?? resoudreCibleOptimisation(choixOptimisationCourant()).motif;
  }

  /** Peint la puce : un bouton par objectif du contrat, l'objectif saisi pressé, et
   *  la phrase du classement dessous. Re-cliquer l'objectif pressé le RETIRE (retour
   *  à « aucun objectif saisi », qui reste un état nommé). */
  function renderCibleChips() {
    const host = cibleHost();
    if (!host) return;
    const saisie = cibleOptimisationSaisie();
    host.innerHTML = '';
    const titre = document.createElement('span');
    titre.className = 'rp9-cible-titre';
    titre.textContent = 'Objectif du classement :';
    host.appendChild(titre);
    for (const c of CIBLES_OPTIMISATION) {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'rp9-cible-chip';
      btn.dataset.cible = c.id;
      btn.textContent = c.label;
      btn.setAttribute('aria-pressed', String(saisie === c.id));
      btn.addEventListener('click', () => {
        poserCibleOptimisation(saisie === c.id ? null : c.id);
        recomputeMatrix();
        renderCibleChips();
      });
      host.appendChild(btn);
    }
    const note = document.createElement('p');
    note.id = 'rp9-cible-note';
    note.className = 'rp9-cible-note';
    note.textContent = motifCible();
    host.appendChild(note);
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
    renderCibleChips(); // CALX114 — l'objectif est saisissable, et il est affiché
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
      // CALX114 — la ligne « Recommandé » dit SELON QUOI elle l'est : le classement
      // n'est plus un objectif implicite qu'il fallait connaître pour lire le tableau.
      const badge = win
        ? ` <span style="color:var(--color-brass-300)">✓ Recommandé · ${esc(libelleCible(matrixResult.cible.appliquee).toLowerCase())}</span>`
        : '';
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
    // W73 — note la matrice sur la MÊME source PVGIS que la carte « reco » : on passe le
    // yieldFn adossé à `ctx.v4YieldCache` (identique à `buildMatrix`/le solveur vivant).
    // Cache vide (PVGIS pas encore résolu) → repli table des DEUX côtés ; une fois PVGIS
    // en cache, la ligne badgée == la config recommandée (plus de désaccord transitoire).
    // CALX114 — le MÊME objectif saisi que l'affinage PVGIS (`optimizer.buildMatrix`) :
    // la ligne badgée et la carte reco ne peuvent pas classer sur deux objectifs.
    ctx.matrixResult = fineGridMatrixV6(ring, ctx.centroidLat, monthlyBill(), obstructionRings(), {
      yieldFn: matrixYieldFn,
      optimisation: choixOptimisationCourant(),
    });
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
