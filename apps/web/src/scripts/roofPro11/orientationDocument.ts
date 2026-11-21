/**
 * ACAL608 — la POSE des modules d'un pan (`geometry.panelOrientation`, et `panels[].orient` en pose
 * mixte) telle que l'atelier l'écrit dans le document : lue du pavage, jamais devinée. Fonction
 * pure ; `prefill.ts::serializeLayout` ne fait que l'appeler.
 */
export type PoseModule = 'portrait' | 'landscape';
export type PoseDuPan = PoseModule | 'mixed';

const estPose = (v: unknown): v is PoseModule => v === 'portrait' || v === 'landscape';

/**
 * `{ panelOrientation }` à émettre pour un pan, ou `{}` (clé omise) quand elle serait inventée :
 * pose absente ou inconnue, aucun module posé, pavage mixte dont un module n'a pas d'`orient`, ou
 * placement libre où un module porte une rotation propre non nulle (`angleDeg`, CALX113).
 * En `mixed`, l'appelant écrit `orient` sur CHAQUE module (`panelOrientation === 'mixed'`).
 */
export function orientationEmise(
  grille: { panelOrientation?: unknown } | null | undefined,
  panneaux: ReadonlyArray<{ orient?: unknown; angleDeg?: unknown }>,
): { panelOrientation?: PoseDuPan } {
  const pose = grille?.panelOrientation;
  if (!panneaux.length) return {};
  if (panneaux.some((p) => typeof p.angleDeg === 'number' && Number.isFinite(p.angleDeg) && p.angleDeg !== 0)) return {};
  if (estPose(pose)) return { panelOrientation: pose };
  if (pose === 'mixed' && panneaux.every((p) => estPose(p.orient))) return { panelOrientation: 'mixed' };
  return {};
}
