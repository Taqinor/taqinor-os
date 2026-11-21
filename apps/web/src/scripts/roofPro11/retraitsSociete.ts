/**
 * ACAL562 — pose d'office, à la fermeture d'un pan, le retrait SUPPLÉMENTAIRE de la table de la
 * société (`degagements.retraits_par_arete`, ACAL561) sur chaque arête typée qui n'en porte pas.
 *
 * Discipline (la même que `jeuReglages.appliquerJeuAuPan`) : posé UNE fois, la saisie prime. Une
 * arête au `retraitM` saisi (sans marque) reste intacte ; une arête posée par la société porte
 * `retraitOrigine: 'societe'`, ce qui permet de la remplacer quand son type change. Sans table :
 * aucun changement. Une arête de type `inconnue` ou absent de la table n'en reçoit aucun.
 * Aucune valeur par défaut : seule la table saisie fait foi.
 */
import { deduceEdgeTypes, type EdgeDeductionZone, type EdgeType, type SerializedEdge } from './edges';
import { type Ctx } from './context';

export type TableRetraits = Partial<Record<EdgeType, number>>;

/** La table de la société lue dans la section `degagements` servie ; vide = aucun retrait posé. */
export function lireTableRetraits(degagements: unknown): TableRetraits {
  const liste = (degagements as { retraits_par_arete?: unknown } | null | undefined)?.retraits_par_arete;
  const table: TableRetraits = {};
  if (!Array.isArray(liste)) return table;
  for (const e of liste as Array<{ type?: unknown; retrait_m?: unknown }>) {
    if (typeof e?.type === 'string' && typeof e.retrait_m === 'number' && Number.isFinite(e.retrait_m) && e.retrait_m >= 0) {
      table[e.type as EdgeType] = e.retrait_m;
    }
  }
  return table;
}

/** L'arête `saisie` (ou rien) complétée du retrait de la société pour son type ; `edges`
 *  conserve ce qui existe, `inconnues` compte les arêtes dont le type n'a pas pu être déduit. */
export function poserRetraitsSociete(
  existantes: readonly SerializedEdge[] | undefined,
  deduites: readonly SerializedEdge[],
  table: TableRetraits,
): { edges: SerializedEdge[] | undefined; inconnues: number } {
  if (!Object.keys(table).length) return { edges: existantes ? [...existantes] : undefined, inconnues: 0 };
  const parIndex = new Map<number, SerializedEdge>();
  for (const e of existantes ?? []) parIndex.set(e.index, e);
  let inconnues = 0;
  for (const d of deduites) {
    const saisie = parIndex.get(d.index);
    const type = saisie?.manuel === true ? saisie.type : d.type;
    if (type === 'inconnue') {
      inconnues += 1;
      continue;
    }
    const aSaisi = saisie?.retraitM != null && saisie.retraitOrigine !== 'societe';
    const valeur = table[type];
    if (aSaisi || valeur === undefined) continue;
    parIndex.set(d.index, { ...(saisie ?? { index: d.index, type }), type, retraitM: valeur, retraitOrigine: 'societe' });
  }
  return { edges: [...parIndex.values()].sort((a, b) => a.index - b.index), inconnues };
}

/** À la fermeture du pan ACTIF : pose les retraits de la société sur ses arêtes. Renvoie la
 *  ligne d'état à dire (types inconnus) ou `null`. */
export function poserRetraitsSurPanActif(ctx: Ctx): string | null {
  const table = lireTableRetraits(ctx.opts?.reglagesAtelier?.degagements);
  const actif = ctx.activeArea();
  if (!actif || ctx.vertices.length < 3 || !Object.keys(table).length) return null;
  const zone = (a: { vertices: EdgeDeductionZone['vertices']; roofType: EdgeDeductionZone['roofType']; facingAzimuthDeg: number; pitchDeg?: number }): EdgeDeductionZone => ({
    vertices: a.vertices,
    roofType: a.roofType ?? 'flat',
    facingAzimuthDeg: a.facingAzimuthDeg ?? 180,
    ...(typeof a.pitchDeg === 'number' && Number.isFinite(a.pitchDeg) ? { pitchDeg: a.pitchDeg } : {}),
  });
  const moi = zone({ vertices: ctx.vertices, roofType: ctx.roofType, facingAzimuthDeg: ctx.facingAzimuthDeg, pitchDeg: ctx.pitchDeg });
  const autres = ctx.areas.filter((a) => a.id !== actif.id).map((a) => zone(a));
  const { edges, inconnues } = poserRetraitsSociete(actif.edges, deduceEdgeTypes(moi, autres), table);
  if (edges) actif.edges = edges;
  return inconnues
    ? `${inconnues} arête${inconnues > 1 ? 's' : ''} de type inconnu : aucun retrait de la société posé`
    : null;
}
