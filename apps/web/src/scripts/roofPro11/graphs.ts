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

  return { renderYearGraph, renderMonthGraph, renderDayGraph };
}
