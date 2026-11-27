// Nouveau fichier car : scene3d.ts est un fichier gelé (C20) — test « pose masquée » (ACAL1945), sorti tel quel.

/** ACAL1945 (revue) — l'étape Toit du Guidé (`data-pose-masquee` sur la coque) ne montre AUCUN panneau : ce test est lu par
 *  le point de passage unique des panneaux de la scène (`buildZoneMeshes`), donc la première pose de l'optimiseur
 *  (`optimizer.ts` → `renderScene`) est couverte comme les rendus de l'éditeur de disposition. */
export function poseMasqueeSurCoque(doc: Document | undefined = typeof document === 'undefined' ? undefined : document): boolean {
  return !!doc?.querySelector?.('.cal-coque[data-pose-masquee]');
}
/** La cellule `i` du pavage est-elle dessinée ? Jamais quand la pose est masquée. */
export function celluleDessinee(i: number, occupiedSet: Set<number> | undefined, count: number, masquee: boolean): boolean {
  if (masquee) return false;
  return occupiedSet ? occupiedSet.has(i) : i < Math.max(0, count);
}
