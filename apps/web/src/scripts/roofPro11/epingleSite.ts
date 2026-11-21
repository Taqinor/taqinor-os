/**
 * Acceptation ACAL490 (ACAL399) — L'ÉPINGLE DU SITE NE SUIT PAS UN PAN VIDE.
 *
 * `serializeLayout` émettait `pin` = centroïde du pan ACTIF. Après « + Ajouter une zone », le pan
 * actif est vide : le document partait avec `pin: null` — simulation refusée (« site.pin ») et
 * « Pas de position GPS sur la fiche » à la réouverture. Ordre, sans rien inventer : le pan actif
 * tracé ; sinon l'épingle du document RELU ; sinon le premier pan tracé ; sinon `null`.
 */
type Point = { lat: number; lng: number };

export function epingleDuSite(actif: Point | null, documentRelu: unknown, premierPanTrace: Point | null): Point | null {
  if (actif) return actif;
  const relue = (documentRelu as { pin?: Partial<Point> | null } | null | undefined)?.pin;
  if (relue && Number.isFinite(relue.lat) && Number.isFinite(relue.lng)) return { lat: relue.lat as number, lng: relue.lng as number };
  return premierPanTrace;
}
