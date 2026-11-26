// ACAL510 — « Pan existant » : modules déjà en place, année de mise en service SAISIE. PUR.
// `motifPanExistant` est le texte UNIQUE du refus (ACAL574 l'importe).
// ACAL1900 — même famille : une pose RELUE du document (ou éditée à la main) est elle aussi
// « déjà en place » : un recalcul de fond ne la re-pose pas (`poseTenue`), et son écart à la
// cible est DIT (`noteEcartPoseRelue`), jamais appliqué (D-ACAL-75).
import { areaLabel } from '../../lib/roofAreas';
import type { AreaRecord, CardData } from './types';
import { annualSavingsMad } from '../../lib/estimatorBrainV2'; // ACAL1900 — économies de la pose tenue, plafonnées
import type { Ctx } from './context';
import { cibleDeLAtelier } from './affichageErp'; // T4-X8-012 (une cible)
import { createLayoutState, type LayoutState } from '../../lib/layoutVariability'; // ACAL1900
import { resnapEnMasse } from './layoutResnap'; // ACAL1900 — même re-snap que W79
import { checkRect, FREE_EDGE_EPS_M, hardViolationsFor, panelCornersFor, rectOfPanel, toUV, type FreeGeom, type FreeLayoutState, type FreePanel } from '../../lib/freeLayout'; // ACAL2032
import type { LayoutPlan } from './types'; // ACAL2032
import { DEG2M, DEG2RAD } from './constants'; // ACAL2032
import { estLePlus } from './affichageErp'; // T4-X8-012

/** ACAL1900 — l'atelier ERP (`opts.chiffrage` défini, `null` compris) affiche une pose à TENIR face à
 *  un recalcul de fond : une disposition posée (relue du document, éditée, remplie) ou un placement libre.
 *  `layoutState` n'existe que dans ces cas : tout rendu de l'optimiseur le remet à `null` (scene3d).
 *  Site public : toujours faux (son comportement ne change pas). */
export function poseTenue(ctx: Pick<Ctx, 'layoutState' | 'freeMode' | 'freeState'> & { opts?: { chiffrage?: unknown } }): boolean {
  if (ctx.opts?.chiffrage === undefined) return false;
  return Boolean(ctx.layoutState) || Boolean(ctx.freeMode && ctx.freeState?.panels.length);
}

/** ACAL1900 — un REDESSIN (ombrage relu au boot, soleil, horizon, bande climatique) ne re-pose jamais une pose tenue :
 *  les chiffres du plan sont recalculés (`resoudre` = renderActive : dérate, horizon, bande climatique), puis la pose
 *  tenue est REMISE (`remettreSurLePlan`) et re-rendue (`rendrePoseTenue` = renderCustomLayout, la carte la suit).
 *  Sans pose tenue, ou sans `rendrePoseTenue` (site public) : `resoudre` seul, comme avant. */
export function redessinerSansReposer(ctx: Parameters<typeof poseTenue>[0] & Pick<Ctx, 'layoutPlan'> & Partial<Pick<Ctx, 'areas' | 'activeAreaId'>>, resoudre: () => void, rendrePoseTenue?: () => void): void {
  // ACAL1920 — pan EXISTANT, pose affichée : le solveur ne fait que refuser (`refusPanExistant`) et le DIRE dans la barre
  // d'état — dès l'ouverture, l'ombrage relu redessinant. Un redessin n'est pas un geste : la pose est redessinée, muette.
  if (ctx.layoutPlan && motifPanExistant(ctx.areas?.find((a) => a.id === ctx.activeAreaId))) return void rendrePoseTenue?.();
  if (!rendrePoseTenue || !poseTenue(ctx)) return void resoudre();
  const tenue = ctx.layoutState;
  resoudre();
  if (tenue) ctx.layoutState = remettreSurLePlan(tenue, ctx.layoutPlan?.grid.panels ?? []);
  rendrePoseTenue();
}

/** ACAL1900 — la pose tenue sur les cellules du plan rendu : mêmes cellules ⇒ la pose telle quelle ; plan changé ⇒ chaque
 *  panneau re-snappé sur la cellule libre la plus proche (comme W79, `resnapEnMasse`) ; aucun plan ⇒ `null`. */
export function remettreSurLePlan(tenue: LayoutState, panneaux: readonly { cx: number; cy: number }[]): LayoutState | null {
  if (!panneaux.length) return null;
  const memes = panneaux.length === tenue.cells.length && panneaux.every((p, i) => Math.abs(p.cx - tenue.cells[i].cx) < 1e-6 && Math.abs(p.cy - tenue.cells[i].cy) < 1e-6);
  if (memes) return tenue;
  const neuf = createLayoutState(panneaux, 0);
  for (const i of resnapEnMasse(neuf.cells, [...tenue.occupied].map((k) => tenue.cells[k]))) neuf.occupied.add(i);
  return neuf;
}

/** ACAL2032 — une pose en PLACEMENT LIBRE face au re-pavage d'un toit, d'un module ou d'un obstacle changé (`recalc`) :
 *  chaque panneau est d'abord ramené au repère du nouveau pavage (l'origine suit le centre du toit), puis GARDÉ s'il
 *  respecte encore les contraintes dures (contour, obstacles, panneaux déjà gardés) ; les autres sont remis sur les
 *  cellules libres du plan rendu (`remettreSurLePlan`, le re-snap unique), et ceux qui n'y trouvent plus de place sont
 *  retirés. Jamais un panneau laissé hors du pan en silence : la phrase dit combien ont bougé. */
export function tenirPoseLibre(etat: FreeLayoutState, g: FreeGeom, plan: Pick<LayoutPlan, 'pack' | 'grid'>, origineAvant?: readonly [number, number]): { etat: FreeLayoutState; gardes: number; deplaces: number; retires: number } {
  const o = plan.pack.origin;
  const [dx, dy] = origineAvant ? [(origineAvant[0] - o[0]) * DEG2M * Math.cos(o[1] * DEG2RAD), (origineAvant[1] - o[1]) * DEG2M] : [0, 0];
  const ringUV = g.ringENU.map(([x, y]) => toUV(g, x, y));
  const gardes: FreeLayoutState = { panels: [] };
  const aReposer: FreePanel[] = [];
  // Mêmes contrôles DURS que le glissé libre (`checkRect`), le rectangle rentré d'un millimètre : le pavage pose ses rangées
  // BORD CONTRE BORD avec le contour, et le bruit des axes (azimut 180°) y voyait une arête « traversante ». Panneau tourné :
  // ses quatre coins.
  const e = FREE_EDGE_EPS_M;
  const tient = (q: FreePanel) => {
    if (q.angleDeg) return !hardViolationsFor(g, ringUV, panelCornersFor(g, q), gardes.panels.map((k) => panelCornersFor(g, k)), []).length;
    const r = rectOfPanel(g, q);
    return !checkRect(gardes, g, { u0: r.u0 + e, u1: r.u1 - e, v0: r.v0 + e, v1: r.v1 - e }, { setbackM: 0, gapM: 0 }).hard;
  };
  for (const p of etat.panels) {
    const q = dx || dy ? { ...p, cx: p.cx + dx, cy: p.cy + dy } : p;
    (tient(q) ? gardes.panels : aReposer).push(q);
  }
  const libres = plan.grid.panels.filter((c) => tient(c));
  const remis = aReposer.length ? remettreSurLePlan(createLayoutState(aReposer, aReposer.length), libres) : null;
  const deplaces = remis ? [...remis.occupied].map((i) => ({ cx: remis.cells[i].cx, cy: remis.cells[i].cy, ...(remis.cells[i].face ? { face: remis.cells[i].face } : {}) })) : [];
  return { etat: { panels: [...gardes.panels, ...deplaces] }, gardes: gardes.panels.length, deplaces: deplaces.length, retires: aReposer.length - deplaces.length };
}

/** ACAL2032 — la phrase de `tenirPoseLibre` (note de la disposition). */
export function phrasePoseLibreTenue(r: { gardes: number; deplaces: number; retires: number }, fmt: (n: number) => string): string {
  if (!r.deplaces && !r.retires) return `Placement libre conservé — ${fmt(r.gardes)} panneaux inchangés.`;
  const s = (n: number) => (n > 1 ? 's' : '');
  const parts = [`${fmt(r.gardes)} panneau${r.gardes > 1 ? 'x' : ''} gardé${s(r.gardes)} à ${r.gardes > 1 ? 'leur' : 'sa'} place`];
  if (r.deplaces) parts.push(`${fmt(r.deplaces)} déplacé${s(r.deplaces)} sur l’emplacement libre le plus proche`);
  if (r.retires) parts.push(`${fmt(r.retires)} retiré${s(r.retires)} (plus de place sur le toit)`);
  return `Placement libre après la modification — ${parts.join(', ')}.`;
}

/** ACAL1900 — la carte de résultat d'une pose TENUE de `n` panneaux, tirée de la carte du MÊME plan (même rendement par
 *  panneau, comme la fenêtre de production de `renderCustomLayout` : seul le NOMBRE change) ; économies plafonnées à
 *  la consommation comme partout. `null` quand rien ne change (même nombre) ou que la carte de départ n'a aucun panneau. */
export function carteDeLaPoseTenue(d: CardData, n: number, fmt: (n: number) => string): CardData | null {
  if (!(d.count > 0) || !(n >= 0) || n === d.count) return null;
  const r = n / d.count;
  const annualKwh = d.annualKwh * r;
  const target = d.target ?? 0;
  const eco = annualSavingsMad(annualKwh, target);
  const why = `Pose tenue : ${fmt(n)} panneaux sur ce plan, telle qu’enregistrée ou posée à la main — même rendement par panneau que la proposition (${fmt(d.count)}).`;
  return { ...d, isReco: false, tenue: true, count: n, kwc: d.kwc * r, annualKwh, pct: target > 0 ? (annualKwh / target) * 100 : 0, savingsLow: eco.low, savingsHigh: eco.high, why };
}

/** ACAL1900 — la phrase de l'écart entre la pose RELUE (ou tenue, `rouverte` faux) et la cible, ou `null` (pas de cible, ou égales). */
export function noteEcartPoseRelue(poses: number, cible: number, fmt: (n: number) => string, rouverte = true, auDevis = ''): string | null {
  if (!(cible > 0) || !(poses > 0) || poses === cible || estLePlus(cible)) return null; // T4-X8-012 — jamais comparé au plafond « le plus »
  const ecart = poses - cible;
  return `${fmt(poses)} posés / ${fmt(cible)} cible${auDevis} — ${rouverte ? 'pose enregistrée rouverte' : 'pose tenue'} telle quelle `
    + `(${fmt(Math.abs(ecart))} de ${ecart > 0 ? 'plus' : 'moins'} que la cible, rien n’est retiré ni ajouté).`;
}

/** Année saisie : vide ⇒ `null` (non saisie) ; entier ≥ 1 et ≤ l'année courante ; sinon refus nommé. */
export function anneeValide(saisie: string, anneeCourante = new Date().getFullYear()): { ok: true; annee: number | null } | { ok: false; motif: string } {
  const s = String(saisie ?? '').trim();
  if (!s) return { ok: true, annee: null };
  const n = Number(s);
  if (!Number.isInteger(n) || n < 1) return { ok: false, motif: 'Année de mise en service : un nombre entier (ex. 2019).' };
  if (n > anneeCourante) return { ok: false, motif: `Année de mise en service : au plus ${anneeCourante}.` };
  return { ok: true, annee: n };
}

/** Le refus d'un geste sur les modules d'un pan existant, ou `null` s'il est modifiable. */
export function motifPanExistant(pan: Pick<AreaRecord, 'existant'> | null | undefined, index = 0): string | null {
  if (!pan?.existant) return null;
  return `${areaLabel(index)} : pan existant (déjà posé) — ses modules ne se modifient pas ; décochez « Pan existant » pour le modifier`;
}

/** ACAL1900 — écrit l'écart de `noteEcartPoseRelue` dans la note du nombre de panneaux (`rp9-need-note`) ; rien sans écart ni note. */
export function direEcartPoseRelue(poses: number, cible: number, fmt: (n: number) => string, rouverte = true, auDevis = ''): void {
  const note = noteEcartPoseRelue(poses, cible, fmt, rouverte, auDevis);
  const el = note && typeof document !== 'undefined' ? document.getElementById('rp9-need-note') : null;
  if (el && note) el.textContent = note;
}

/** T4-X8-012 (une cible) — `direEcartPoseRelue` contre LA cible servie (comptée dans le module posé `watt`) et sa source, dans les
 *  mots de la carte « Cible — panneaux » ; sans cible servie : le nombre à poser, comme avant. `suite` = « · K au devis… ». */
export function direEcartALaPose(poses: number, ctx: Pick<Ctx, 'neededPanels'> & Parameters<typeof cibleDeLAtelier>[0], watt: number | null | undefined, fmt: (n: number) => string, rouverte: boolean, suite: string): void {
  const c = cibleDeLAtelier(ctx, watt);
  direEcartPoseRelue(poses, c ? c.panneaux : ctx.neededPanels, fmt, rouverte, `${c ? ` (${c.origine})` : ''}${suite}`);
}
