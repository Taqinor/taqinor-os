/**
 * Rendu SVG des graphes de production (Année / Mois / Jour).
 * Extrait de roof-tool-pro11.ts (split modulaire 2026-06-20) — comportement
 * INCHANGÉ : ces fonctions construisent des chaînes SVG à partir des données de
 * production et de l'état (`ctx.prodMonth`, `ctx.prodSpecificDate`, `ctx.svgBox`).
 */
import {
  yearSeries,
  monthSeries,
  daySeries,
  barGeometry,
  dayCurvePath,
  dayAreaPath,
  fmtKwh,
} from '../../lib/productionWindow';
import { type ScaledProduction } from '../../lib/productionEngine';
import { esc } from './dom';
import { type Ctx } from './context';

export interface Graphs {
  renderYearGraph: (prod: ScaledProduction) => string;
  renderMonthGraph: (prod: ScaledProduction) => string;
  renderDayGraph: (prod: ScaledProduction) => string;
  /** PV75 — mini cascade des pertes (barres horizontales, libellés FR), à partir du
   *  `loss_breakdown` bancable {poste: pct} injecté par la page hôte. SVG autonome
   *  (pas rempli dans le graphe de scope année/mois/jour) ; chaîne vide si aucun poste
   *  de perte exploitable (tous nuls/absents). */
  renderLossCascade: (lossBreakdown: Record<string, number>) => string;
}

// PV75 — libellés FR des postes de perte connus (mêmes postes que
// `apps/ventes/solar_design.py::DEFAULT_LOSS_FACTORS` côté serveur). Un poste absent
// de cette table (extensibilité serveur) affiche sa clé brute — jamais une erreur.
const LOSS_LABELS_FR: Record<string, string> = {
  temperature: 'Température',
  soiling: 'Salissure',
  shading: 'Ombrage',
  wiring: 'Câblage',
  inverter: 'Onduleur',
  mismatch: 'Dispersion',
  availability: 'Disponibilité',
};

function lossLabelFr(poste: string): string {
  return LOSS_LABELS_FR[poste] ?? poste;
}

export function createGraphs(ctx: Ctx): Graphs {
  const SVG_BOX = ctx.svgBox;

  /** Graphe ANNÉE : 12 barres mensuelles (kWh/mois), étiquettes mensuelles courtes. */
  function renderYearGraph(prod: ScaledProduction): string {
    const { bars } = yearSeries(prod);
    const rects = barGeometry(bars, SVG_BOX, 0.25);
    const baseY = SVG_BOX.height - SVG_BOX.padBottom;
    const bodies = rects
      .map(
        (r) =>
          `<rect x="${r.x.toFixed(2)}" y="${r.y.toFixed(2)}" width="${r.width.toFixed(2)}" height="${r.height.toFixed(2)}" rx="1.5" fill="var(--color-brass-400, #e8b54a)"><title>${esc(r.label)} : ${esc(fmtKwh(r.kwh))}</title></rect>`,
      )
      .join('');
    // Les barres portent déjà l'étiquette mensuelle courte (« janv. »…) via yearSeries.
    const labels = rects
      .map(
        (r) =>
          `<text x="${(r.x + r.width / 2).toFixed(2)}" y="${(SVG_BOX.height - 5).toFixed(2)}" text-anchor="middle" font-size="7" fill="var(--color-lune-faint, #6f7791)">${esc(r.label)}</text>`,
      )
      .join('');
    return `<line x1="${SVG_BOX.padLeft}" y1="${baseY}" x2="${SVG_BOX.width - SVG_BOX.padRight}" y2="${baseY}" stroke="var(--color-white, #fff)" stroke-opacity="0.12" stroke-width="1"/>${bodies}${labels}`;
  }

  /** Graphe MOIS : ~N barres journalières (kWh/jour) du mois sélectionné. */
  function renderMonthGraph(prod: ScaledProduction): string {
    const { bars } = monthSeries(prod, ctx.prodMonth);
    const rects = barGeometry(bars, SVG_BOX, 0.15);
    const baseY = SVG_BOX.height - SVG_BOX.padBottom;
    const bodies = rects
      .map(
        (r) =>
          `<rect x="${r.x.toFixed(2)}" y="${r.y.toFixed(2)}" width="${r.width.toFixed(2)}" height="${r.height.toFixed(2)}" fill="var(--color-brass-400, #e8b54a)"><title>jour ${esc(r.label)} : ${esc(fmtKwh(r.kwh))}</title></rect>`,
      )
      .join('');
    // Étiquettes clairsemées (1, milieu, dernier) pour éviter l'encombrement.
    const last = rects.length;
    const ticks = last > 0 ? [0, Math.floor(last / 2), last - 1] : [];
    const labels = ticks
      .map((i) => {
        const r = rects[i];
        if (!r) return '';
        return `<text x="${(r.x + r.width / 2).toFixed(2)}" y="${(SVG_BOX.height - 5).toFixed(2)}" text-anchor="middle" font-size="7" fill="var(--color-lune-faint, #6f7791)">${esc(r.label)}</text>`;
      })
      .join('');
    return `<line x1="${SVG_BOX.padLeft}" y1="${baseY}" x2="${SVG_BOX.width - SVG_BOX.padRight}" y2="${baseY}" stroke="var(--color-white, #fff)" stroke-opacity="0.12" stroke-width="1"/>${bodies}${labels}`;
  }

  /** Graphe JOUR : courbe 24 h de puissance (kW) + aire remplie. */
  function renderDayGraph(prod: ScaledProduction): string {
    const { points } = daySeries(prod, ctx.prodMonth, ctx.prodSpecificDate);
    const area = dayAreaPath(points, SVG_BOX);
    const line = dayCurvePath(points, SVG_BOX);
    const baseY = SVG_BOX.height - SVG_BOX.padBottom;
    // Repères d'heures (0, 6, 12, 18, 23 h).
    const plotW = SVG_BOX.width - SVG_BOX.padLeft - SVG_BOX.padRight;
    const xAt = (h: number) => SVG_BOX.padLeft + (h / 23) * plotW;
    const ticks = [0, 6, 12, 18, 23]
      .map(
        (h) =>
          `<text x="${xAt(h).toFixed(2)}" y="${(SVG_BOX.height - 5).toFixed(2)}" text-anchor="middle" font-size="7" fill="var(--color-lune-faint, #6f7791)">${h}h</text>`,
      )
      .join('');
    const areaEl = area
      ? `<path d="${area}" fill="var(--color-brass-400, #e8b54a)" fill-opacity="0.18"/>`
      : '';
    const lineEl = line
      ? `<path d="${line}" fill="none" stroke="var(--color-brass-400, #e8b54a)" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>`
      : '';
    return `<line x1="${SVG_BOX.padLeft}" y1="${baseY}" x2="${SVG_BOX.width - SVG_BOX.padRight}" y2="${baseY}" stroke="var(--color-white, #fff)" stroke-opacity="0.12" stroke-width="1"/>${areaEl}${lineEl}${ticks}`;
  }

  /** PV75 — mini cascade des pertes : une barre horizontale par poste, longueur
   *  proportionnelle au poste le plus lourd, libellé FR à gauche, pourcentage à
   *  droite. Indépendante de `ctx` (pure fonction du payload bancable de la page hôte). */
  function renderLossCascade(lossBreakdown: Record<string, number>): string {
    const entries = Object.entries(lossBreakdown || {}).filter(
      ([, pct]) => Number.isFinite(pct) && pct > 0,
    );
    if (entries.length === 0) return '';
    const maxPct = Math.max(...entries.map(([, pct]) => pct));
    const width = 280;
    const rowH = 16;
    const labelW = 88;
    const valueW = 40;
    const barMaxW = width - labelW - valueW;
    const height = entries.length * rowH + 4;
    const rows = entries
      .map(([poste, pct], i) => {
        const y = i * rowH + 2;
        const barW = maxPct > 0 ? Math.max(1, (pct / maxPct) * barMaxW) : 0;
        const label = esc(lossLabelFr(poste));
        const pctTxt = `${pct.toFixed(1)} %`;
        return (
          `<text x="0" y="${(y + 9).toFixed(1)}" font-size="8" fill="var(--color-lune-soft, #b7bdd1)">${label}</text>` +
          `<rect x="${labelW}" y="${y.toFixed(1)}" width="${barW.toFixed(2)}" height="10" rx="1" fill="var(--color-brass-400, #e8b54a)"><title>${label} : ${esc(pctTxt)}</title></rect>` +
          `<text x="${(width - 2).toFixed(1)}" y="${(y + 9).toFixed(1)}" text-anchor="end" font-size="8" fill="var(--color-lune-faint, #6f7791)">${esc(pctTxt)}</text>`
        );
      })
      .join('');
    return `<svg viewBox="0 0 ${width} ${height}" width="100%" role="img" aria-label="Cascade des pertes de production">${rows}</svg>`;
  }

  return { renderYearGraph, renderMonthGraph, renderDayGraph, renderLossCascade };
}
