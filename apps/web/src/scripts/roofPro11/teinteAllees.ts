/**
 * CALX403 câblage — LES MODULES POSÉS EN TRAVERS D'UNE ALLÉE SE VOIENT EN 3D.
 *
 * `obstaclesUi.modulesSurAllees()` COMPTE les modules qui chevauchent une allée de
 * circulation (il n'en supprime aucun — parité Aurora), et le bandeau les nomme. Mais la
 * scène 3D, elle, les peignait comme les autres : le dessinateur lisait « 4 modules posés
 * en travers » sans pouvoir dire LESQUELS.
 *
 * Ce module est le crochet qui manquait, et RIEN D'AUTRE :
 *  - la page hôte dépose UNE source de vérité (`poserSourceCellulesSurAllees`) — les
 *    cellules de lattice des modules chevauchants, qu'elle seule sait relier aux repères ;
 *  - `scene3d.ts` appelle `teinterAllees(...)` à la fin de son bloc de panneaux, sur le
 *    buffer `instanceColor` que W88 pose déjà (aucun mesh neuf, aucun draw-call de plus).
 *
 * Sans source déposée, la fonction ne touche RIEN : la scène d'aujourd'hui, octet pour
 * octet. Un survol/une sélection (`setPanelSelection`) ou la carte d'accès solaire
 * (`setSolarAccessHeatmap`) repassent sur le même buffer et reprennent la main : la
 * teinte d'allée est une marque de RENDU, pas un état.
 */
import { type Ctx } from './context';

/** CONVENTION DE DESSIN — jaune. Multiplie la couleur diffuse du panneau (même canal que
 *  le laiton du survol) : la valeur ne dit rien du produit, elle ne fait que signaler. */
export const TEINTE_ALLEE: Readonly<{ r: number; g: number; b: number }> = {
  r: 1,
  g: 0.85,
  b: 0.25,
};

/** Le buffer de couleurs d'instances, vu par ce module (structure de `InstancedBufferAttribute`). */
export interface BufferTeinte {
  setXYZ(index: number, x: number, y: number, z: number): unknown;
  needsUpdate: boolean;
}

/** Le mesh instancié des panneaux, vu par ce module. */
export interface MeshTeintable {
  instanceColor?: BufferTeinte | null;
}

/** La source déposée par la page hôte : les cellules de lattice des modules qui
 *  chevauchent une allée, relues À CHAQUE RENDU (une allée tracée entre deux rendus
 *  doit se voir sans re-câblage). */
type SourceCellules = (() => Iterable<number>) | null;

interface CtxAllees {
  cellulesSurAllees?: SourceCellules;
}

/**
 * La page hôte déclare OÙ lire les cellules sur allée. `null` retire la source : plus
 * aucune teinte n'est posée (et non « plus aucune allée », qui serait un mensonge).
 */
export function poserSourceCellulesSurAllees(ctx: Ctx, source: SourceCellules): void {
  (ctx as unknown as CtxAllees).cellulesSurAllees = source ?? null;
}

/** Les cellules sur allée à cet instant. Aucune source, ou une source qui jette :
 *  ensemble VIDE — jamais un module signalé au hasard. */
export function cellulesSurAllees(ctx: Ctx): Set<number> {
  const source = (ctx as unknown as CtxAllees).cellulesSurAllees;
  if (typeof source !== 'function') return new Set();
  try {
    const cellules = new Set<number>();
    for (const c of source() ?? []) {
      if (typeof c === 'number' && Number.isFinite(c)) cellules.add(c);
    }
    return cellules;
  } catch {
    return new Set();
  }
}

/**
 * Teinte les instances dont la cellule de lattice est sur une allée, et laisse les autres
 * EXACTEMENT comme elles étaient (aucune remise à blanc : ce module n'efface pas le
 * surlignage de quelqu'un d'autre). Renvoie le nombre d'instances teintées — 0 quand il
 * n'y a rien à signaler, ce qui est aussi le cas « pas de mesh ».
 */
export function teinterAllees(
  ctx: Ctx,
  mesh: MeshTeintable | null | undefined,
  cellulesParInstance: readonly number[] | null | undefined,
): number {
  const buffer = mesh?.instanceColor;
  if (!buffer || !Array.isArray(cellulesParInstance) || !cellulesParInstance.length) return 0;
  const surAllee = cellulesSurAllees(ctx);
  if (!surAllee.size) return 0;
  let teintees = 0;
  for (let i = 0; i < cellulesParInstance.length; i++) {
    if (!surAllee.has(cellulesParInstance[i])) continue;
    buffer.setXYZ(i, TEINTE_ALLEE.r, TEINTE_ALLEE.g, TEINTE_ALLEE.b);
    teintees++;
  }
  if (teintees) buffer.needsUpdate = true;
  return teintees;
}
