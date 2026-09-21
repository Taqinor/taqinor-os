/**
 * CAL84 — statistiques PAR PAN (modules, kWc, orientation, pente, surface utile, taux
 * d'occupation), totalisées par bâtiment (CAL59) puis par site. Géométrie PURE (aucun
 * Three, aucun DOM) : toutes les colonnes sont CALCULÉES depuis la géométrie/le résultat
 * déjà connus — rien n'est saisi ici, rien n'est inventé.
 */
import { geodesicAreaM2, PANEL_LENGTH_M, PANEL_WIDTH_M } from '../../lib/roof';
// CALX126 — formatage FR + échappement partagés (chaînes pures : ce module reste sans DOM).
import { esc as escHtml, fmt } from './dom';
import { type AreaResult } from '../../lib/roofAreas';
import { type AreaRecord } from './types';
// CALX110 — le kWc d'un pan vient de SON module, et la mention « plusieurs modèles »
// est prononcée par la seule fonction qui sait la prononcer (`moduleSelect.ts`).
import {
  kwcDuPan,
  syntheseModules,
  type ModuleDocument,
  type SyntheseModules,
} from './moduleSelect';

/** Surface au sol (m²) d'UN panneau — même constante physique que le reste de l'outil
 *  (PANEL_LENGTH_M × PANEL_WIDTH_M). Sert à CALCULER le taux d'occupation, jamais à
 *  dimensionner un pavage. */
export const PANEL_FOOTPRINT_M2 = PANEL_LENGTH_M * PANEL_WIDTH_M;

export interface PanStat {
  id: string;
  label: string;
  buildingId: string | null;
  panels: number;
  kwc: number;
  azimuthDeg: number | null;
  pitchDeg: number | null;
  /** Surface utile du pan (m²), déduite du contour tracé. 0 si aucun contour (< 3 sommets). */
  areaM2: number;
  /** Taux d'occupation (0–1) : surface au sol des panneaux posés / surface utile.
   *  null si le pan n'a pas de surface exploitable (division par zéro évitée). */
  occupancyRate: number | null;
  /** Motif d'un pan à ZÉRO panneau (jamais un total vide sans explication). '' si le
   *  pan porte des panneaux. */
  zeroReason: string;
  /** CALX110 — le modèle de module posé sur CE pan (`id` du catalogue), ou `null` quand
   *  le pan reste sur le module par défaut de l'atelier. Additif : une colonne de plus,
   *  jamais une colonne changée. */
  moduleId: string | null;
  /** CALX110 — son libellé, pour que l'écran NOMME le modèle au lieu d'un identifiant. */
  moduleLibelle: string | null;
}

export interface BuildingTotal {
  buildingId: string | null;
  panels: number;
  kwc: number;
  areaM2: number;
}

export interface PanStatsResult {
  pans: PanStat[];
  byBuilding: BuildingTotal[];
  site: BuildingTotal;
  /** CALX110 — la synthèse des modèles posés sur le site : watt du modèle majoritaire,
   *  « plusieurs modèles » dès que les pans divergent, et la mention à afficher. Sans
   *  résolveur de module, elle décrit le module unique d'aujourd'hui. */
  modules: SyntheseModules;
}

/** Une ligne par pan : `resultFor(a)` fournit le résultat (live pour la zone active,
 *  snapshot sinon) — injecté pour rester pur (aucun accès à `ctx` ici).
 *
 *  CALX110 — `moduleFor` (OPTIONNEL) donne le module posé sur chaque pan. Absent, tout se
 *  comporte comme avant : le kWc reste celui du résultat de zone et l'empreinte celle du
 *  module unique. Présent, le kWc d'un pan vaut `nombre × puissance de SON module` — c'est
 *  ce qui empêche deux modèles de rendre le même kWc — et le taux d'occupation se mesure
 *  sur l'empreinte RÉELLE de ce module. Un module sans puissance ne fabrique aucun chiffre :
 *  le kWc du résultat de zone reste affiché tel quel. */
export function computePanStats(
  areas: readonly AreaRecord[],
  resultFor: (a: AreaRecord) => AreaResult | null,
  moduleFor?: (a: AreaRecord) => ModuleDocument | null,
): PanStatsResult {
  const modulesParPan: Record<string, string | undefined> = {};
  const catalogue: ModuleDocument[] = [];
  const pans: PanStat[] = areas.map((a) => {
    const r = resultFor(a);
    const areaM2 = a.vertices.length >= 3 ? geodesicAreaM2(a.vertices) : 0;
    const panels = r?.panels ?? 0;
    const modulePan = moduleFor?.(a) ?? null;
    if (modulePan) {
      modulesParPan[a.id] = modulePan.id;
      if (!catalogue.some((m) => m.id === modulePan.id)) catalogue.push(modulePan);
    }
    // CALX110 — la puissance de CE module fait foi ; si elle manque, on n'invente rien et
    // le chiffre déjà calculé pour la zone reste celui qui s'affiche.
    const kwc = (modulePan ? kwcDuPan(panels, modulePan) : null) ?? r?.kwc ?? 0;
    const empreinteM2 = modulePan && modulePan.longueurMm && modulePan.largeurMm
      ? (modulePan.longueurMm * modulePan.largeurMm) / 1e6
      : PANEL_FOOTPRINT_M2;
    const occupancyRate = areaM2 > 0 ? (panels * empreinteM2) / areaM2 : null;
    let zeroReason = '';
    if (panels <= 0) {
      zeroReason = a.vertices.length < 3 ? 'toit non tracé' : r ? 'aucun panneau ne tient (obstacles/retraits)' : 'à calculer';
    }
    return {
      id: a.id,
      label: a.label,
      buildingId: a.buildingId ?? null,
      panels,
      kwc,
      azimuthDeg: a.roofType === 'pitched' ? a.facingAzimuthDeg : null,
      pitchDeg: a.roofType === 'pitched' ? a.pitchDeg : null,
      areaM2,
      occupancyRate,
      zeroReason,
      moduleId: modulePan?.id ?? null,
      moduleLibelle: modulePan?.libelle ?? null,
    };
  });

  const groupKeys = Array.from(new Set(pans.map((p) => p.buildingId)));
  const byBuilding: BuildingTotal[] = groupKeys.map((buildingId) => {
    const rows = pans.filter((p) => p.buildingId === buildingId);
    return {
      buildingId,
      panels: rows.reduce((s, p) => s + p.panels, 0),
      kwc: rows.reduce((s, p) => s + p.kwc, 0),
      areaM2: rows.reduce((s, p) => s + p.areaM2, 0),
    };
  });

  const site: BuildingTotal = {
    buildingId: null,
    panels: pans.reduce((s, p) => s + p.panels, 0),
    kwc: pans.reduce((s, p) => s + p.kwc, 0),
    areaM2: pans.reduce((s, p) => s + p.areaM2, 0),
  };

  // CALX110 — la mention affichée au-dessus des totaux : elle NOMME les modèles posés, et
  // dit « plusieurs modèles » dès que deux pans divergent. Le catalogue passé ici est celui
  // que les pans désignent vraiment (ordre de première apparition) — aucun modèle du stock
  // qui ne serait posé nulle part n'y entre.
  const modules = syntheseModules(
    { catalogue, parPan: modulesParPan },
    pans.map((p) => ({ id: p.id, panels: p.panels })),
  );

  return { pans, byBuilding, site, modules };
}

/** true si AU MOINS un pan porte un `buildingId` — sinon un seul groupe (site == le
 *  seul « bâtiment »), pas la peine d'afficher des sous-totaux redondants. */
export function hasMultipleBuildings(result: PanStatsResult): boolean {
  return result.byBuilding.length > 1 || (result.byBuilding.length === 1 && result.byBuilding[0].buildingId !== null);
}

/* ════════════════════════════════════════════════════════════════════════════
   CALX126 — TOTALISER LE SITE : LES PANS **ET** LES SURFACES DE POSE.
   ----------------------------------------------------------------------------
   Constat : la table par pan existait (CAL84) et `setAreaBuilding` rattachait
   déjà un pan à son bâtiment (CAL59), mais les surfaces de pose — sol, ombrière,
   façade — ne figuraient dans AUCUN total de l'atelier : seul l'écran Ombrière
   tenait une table par bâtiment, hors atelier. Une toiture, un carport et un
   champ au sol du même site se lisaient donc dans trois endroits différents.

   LA RÈGLE DE CETTE TABLE : elle n'est qu'un ASSEMBLAGE. Les modules d'une
   surface de pose viennent du MOTEUR (`engine.modules`) ; son aire vient du
   contour TRACÉ ; son kWc vient de `kwcDuPan` et de la puissance SAISIE du
   module. Rien n'y est (re)calculé — et toute valeur que le moteur n'a pas
   publiée reste une cellule VIDE, jamais un 0, avec son motif en clair.

   Ce module reste PUR : aucun Three, aucun DOM. `htmlTableSite` rend une CHAÎNE
   que l'écran insère — c'est du texte, pas une manipulation d'arbre.
   ══════════════════════════════════════════════════════════════════════════ */

/**
 * CALX126 — ce qu'une surface de pose (`poseSurfaces[]`, contrat CAL89/CAL91/CALX87)
 * apporte à la table, et rien de plus. Type STRUCTUREL délibéré : `panStats` ne
 * dépend d'aucun module de scène et reste pur.
 */
export interface SurfacePoseLigne {
  kind: string;
  id: string;
  label?: string;
  buildingId?: string;
  areaM2?: number | null;
  engine?: { modules?: number | null } | null;
}

/** Genre d'une ligne de la table du site. */
export type GenreLigneSite = 'pan' | 'sol' | 'ombriere' | 'facade';

/** Libellé FRANÇAIS de chaque genre de ligne — l'écran n'affiche jamais la clé. */
export const LIBELLE_GENRE_LIGNE: Readonly<Record<GenreLigneSite, string>> = {
  pan: 'Pan de toit',
  sol: 'Champ au sol',
  ombriere: 'Ombrière',
  facade: 'Façade',
};

/** Une LIGNE de la table du site : un pan de toit, ou une surface de pose. */
export interface LigneSite {
  id: string;
  label: string;
  genre: GenreLigneSite;
  buildingId: string | null;
  /** Aire (m²). `null` = non mesurée ⇒ cellule VIDE, jamais 0. */
  areaM2: number | null;
  /** Modules posés. `null` = le moteur n'a rien publié ⇒ cellule VIDE. */
  modules: number | null;
  /** Puissance (kWc). `null` = modules ou puissance du module manquants. */
  kwc: number | null;
  /** Pourquoi une cellule est vide, en clair. `''` quand tout est rempli. */
  motif: string;
}

/** Un TOTAL (par bâtiment, ou pour le site). Une somme partielle le DIT. */
export interface TotalSite {
  buildingId: string | null;
  modules: number | null;
  kwc: number | null;
  areaM2: number | null;
  /** Ce qui manque dans ce total, nommé. `''` quand il est complet. */
  motif: string;
}

/** La table du site : une ligne par surface, un total par bâtiment, un total de site. */
export interface SiteStats {
  lignes: LigneSite[];
  parBatiment: TotalSite[];
  site: TotalSite;
}

/** Somme des valeurs CONNUES d'une colonne, et le nombre de cellules vides. */
function sommePartielle(valeurs: readonly (number | null)[]): { total: number | null; manquants: number } {
  let total: number | null = null;
  let manquants = 0;
  for (const v of valeurs) {
    if (v === null) manquants++;
    else total = (total ?? 0) + v;
  }
  return { total, manquants };
}

/** Totalise un groupe de lignes — une somme incomplète est NOMMÉE, pas arrondie à 0. */
function totaliser(buildingId: string | null, lignes: readonly LigneSite[]): TotalSite {
  const modules = sommePartielle(lignes.map((l) => l.modules));
  const kwc = sommePartielle(lignes.map((l) => l.kwc));
  const aire = sommePartielle(lignes.map((l) => l.areaM2));
  const manques: string[] = [];
  if (modules.manquants) manques.push(`${modules.manquants} surface(s) sans plan du moteur`);
  if (kwc.manquants > modules.manquants) manques.push('puissance de module non renseignée');
  if (aire.manquants) manques.push(`${aire.manquants} surface(s) sans contour mesuré`);
  return {
    buildingId,
    modules: modules.total,
    kwc: kwc.total,
    areaM2: aire.total,
    motif: manques.length ? `total partiel — ${manques.join(' ; ')}` : '',
  };
}

/** Le genre d'une surface de pose, ramené aux genres que la table sait nommer. */
function genreLigne(kind: string): GenreLigneSite {
  if (kind === 'sol' || kind === 'ombriere' || kind === 'facade') return kind;
  return 'sol';
}

/**
 * CALX126 — la table du SITE : une ligne par pan de toit ET par surface de pose,
 * plus un total par bâtiment et un total de site.
 *
 * `moduleFor` (OPTIONNEL) donne le module posé sur une surface de pose, pour que
 * son kWc soit `modules × puissance SAISIE` (même règle que les pans, CALX110).
 * Absent, ou fiche sans puissance : le kWc reste VIDE et le motif le dit — jamais
 * un kWc fabriqué à partir d'une puissance supposée.
 */
export function computeSiteStats(
  pans: PanStatsResult,
  surfaces: readonly SurfacePoseLigne[] | null | undefined,
  moduleFor?: (s: SurfacePoseLigne) => ModuleDocument | null,
): SiteStats {
  const lignes: LigneSite[] = pans.pans.map((p) => ({
    id: p.id,
    label: p.label || p.id,
    genre: 'pan' as const,
    buildingId: p.buildingId,
    // Un pan déjà totalisé par CAL84 : ses chiffres sont repris TELS QUELS.
    areaM2: p.areaM2 > 0 ? p.areaM2 : null,
    modules: p.panels,
    kwc: p.kwc,
    motif: p.areaM2 > 0 ? p.zeroReason : 'contour du pan non tracé',
  }));

  for (const s of surfaces ?? []) {
    if (!s || typeof s.id !== 'string' || !s.id.length) continue;
    const modules =
      typeof s.engine?.modules === 'number' && Number.isFinite(s.engine.modules)
        ? s.engine.modules
        : null;
    const module = moduleFor?.(s) ?? null;
    const kwc = modules !== null && module ? kwcDuPan(modules, module) : null;
    const aire = typeof s.areaM2 === 'number' && Number.isFinite(s.areaM2) && s.areaM2 > 0 ? s.areaM2 : null;
    const manques: string[] = [];
    if (modules === null) manques.push('plan du moteur non reçu');
    else if (kwc === null) manques.push('puissance du module non renseignée');
    if (aire === null) manques.push('contour non mesuré');
    lignes.push({
      id: s.id,
      label: s.label || s.id,
      genre: genreLigne(s.kind),
      buildingId: (s.buildingId ?? '').trim() || null,
      areaM2: aire,
      modules,
      kwc,
      motif: manques.join(' ; '),
    });
  }

  const groupes = Array.from(new Set(lignes.map((l) => l.buildingId)));
  return {
    lignes,
    parBatiment: groupes.map((b) => totaliser(b, lignes.filter((l) => l.buildingId === b))),
    site: totaliser(null, lignes),
  };
}

/** Une cellule : le nombre formaté, ou VIDE (jamais 0) quand la valeur manque. */
function cellule(v: number | null, decimales = 0): string {
  if (v === null) return '<span class="text-lune-faint" data-cellule-vide>—</span>';
  return decimales
    ? v.toLocaleString('fr-FR', { maximumFractionDigits: decimales })
    : fmt(Math.round(v));
}

/**
 * CALX126 — la table du site en HTML (chaîne PURE : l'écran l'insère, ce module ne
 * touche jamais l'arbre). Une ligne par surface, un total par bâtiment, un total de
 * site ; chaque cellule vide porte son motif, visible à l'écran.
 */
export function htmlTableSite(stats: SiteStats): string {
  const ligneHtml = (l: LigneSite): string => `<tr data-site-ligne="${escHtml(l.id)}" data-site-genre="${escHtml(l.genre)}">
      <td class="px-2 py-1 text-white">${escHtml(l.label)}</td>
      <td class="px-2 py-1 text-lune-faint">${escHtml(LIBELLE_GENRE_LIGNE[l.genre])}</td>
      <td class="px-2 py-1 text-lune-faint">${escHtml(l.buildingId ?? 'Bâtiment sans id')}</td>
      <td class="px-2 py-1 text-right">${cellule(l.areaM2)}</td>
      <td class="px-2 py-1 text-right">${cellule(l.modules)}</td>
      <td class="px-2 py-1 text-right">${cellule(l.kwc, 2)}</td>
      <td class="px-2 py-1 text-lune-faint">${escHtml(l.motif)}</td>
    </tr>`;
  const totalHtml = (t: TotalSite): string => `<tr data-site-total="${escHtml(t.buildingId ?? '')}" class="border-t border-white/15 font-semibold">
      <td class="px-2 py-1 text-white" colspan="3">Total ${escHtml(t.buildingId ?? 'du site')}</td>
      <td class="px-2 py-1 text-right">${cellule(t.areaM2)}</td>
      <td class="px-2 py-1 text-right">${cellule(t.modules)}</td>
      <td class="px-2 py-1 text-right">${cellule(t.kwc, 2)}</td>
      <td class="px-2 py-1 text-lune-faint">${escHtml(t.motif)}</td>
    </tr>`;
  const corps = stats.parBatiment
    .map(
      (b) =>
        stats.lignes.filter((l) => l.buildingId === b.buildingId).map(ligneHtml).join('') +
        totalHtml(b),
    )
    .join('');
  return `<table data-site-stats class="mt-3 w-full min-w-[620px] border-collapse text-xs text-lune-soft">
      <caption class="pb-1 text-left text-[11px] uppercase tracking-wide text-lune-faint">Site — pans de toit et surfaces de pose</caption>
      <thead>
        <tr class="border-b border-white/15 text-left text-[11px] uppercase tracking-wide text-lune-faint">
          <th class="px-2 py-1">Surface</th>
          <th class="px-2 py-1">Genre</th>
          <th class="px-2 py-1">Bâtiment</th>
          <th class="px-2 py-1 text-right">Aire m²</th>
          <th class="px-2 py-1 text-right">Modules</th>
          <th class="px-2 py-1 text-right">kWc</th>
          <th class="px-2 py-1">Ce qui manque</th>
        </tr>
      </thead>
      <tbody>${corps}</tbody>
    </table>`;
}
