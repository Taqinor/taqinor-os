// ACAL1984 (suite) — l'ŒIL de la caméra de la couche MapLibre. La couche reçoit UNE matrice modèle → écran (projection
// de la carte × matrice du modèle) ; posée telle quelle sur une THREE.Camera IDENTITÉ, le shader croit l'œil à l'origine
// de la scène (sous le toit) : vues rasantes, Fresnel à 1 (verre éteint), diffus assombri en tache au-dessus de l'origine.
// `poserOeil` retrouve l'œil RÉEL (le point que la matrice envoie à w = 0, x = y = 0) et répartit la même matrice en
// vue (translation vers l'œil) × projection : l'image est identique au pixel près, l'éclairage devient juste.
import * as THREE from 'three';
import { presentationClient } from './jeuPresentation';

/** Pose sur `camera` l'œil réel de `modeleVersClip` (perspective) ; rend faux (caméra inchangée) si la matrice
 *  n'est pas inversible ou n'est pas une perspective (œil à l'infini). */
export function poserOeil(camera: THREE.Camera, modeleVersClip: THREE.Matrix4): boolean {
  if (Math.abs(modeleVersClip.determinant()) < 1e-30) return false;
  const oeil = new THREE.Vector4(0, 0, 1, 0).applyMatrix4(modeleVersClip.clone().invert());
  if (!(Math.abs(oeil.w) > 1e-12)) return false;
  camera.position.set(oeil.x / oeil.w, oeil.y / oeil.w, oeil.z / oeil.w);
  camera.quaternion.identity();
  camera.scale.set(1, 1, 1);
  camera.updateMatrixWorld(true);
  camera.projectionMatrix.copy(modeleVersClip).multiply(camera.matrixWorld);
  camera.projectionMatrixInverse.copy(camera.projectionMatrix).invert();
  return true;
}

/** LOT 6 (D-ACAL-136) — le verre SANS vernis et l'œil réel (ACAL1984) : l'atelier ERP (`productionAtelier`), ou la
 *  visionneuse au soleil des liens de confiance quand elle teinte le pan actif (`teinteAccesVisible`, posé par
 *  `viewerFullBoot.ts` seulement) — sans quoi la teinte reste invisible. Absents : site public inchangé. */
export function verreEtOeilAtelier(opts: { productionAtelier?: unknown; teinteAccesVisible?: boolean; presentationClient?: boolean } | null | undefined): boolean {
  return opts?.productionAtelier !== undefined || opts?.teinteAccesVisible === true || presentationClient(opts); // lot 8 : lien de confiance
}

/** T4-U1-017 — pente de carte (degrés) jusqu'à laquelle les hauteurs remontent progressivement (pas de saut au passage
 *  Plan → 3D) ; au-delà, la scène a ses vraies hauteurs. */
export const PENTE_HAUTEURS_PLEINES_DEG = 10;
/** T4-U1-017 — facteur des hauteurs en vue Plan : 6 m de bâtiment → 6 cm (l'ordre de profondeur des faces est gardé). */
export const ECRASEMENT_PLAN = 0.01;

/** T4-U1-017 — la matrice à appliquer au modèle selon la pente : en Plan (pente 0), les hauteurs sont écrasées (la caméra de
 *  la carte est une perspective : un toit à 6 m de haut sortait grossi autour du centre de la carte, hors du contour tracé au
 *  sol) ; elles remontent avec la pente et sont entières dès 10° (vues 3D : identité). */
export function aplatirEnPlan(penteDeg: number): THREE.Matrix4 {
  const p = Number.isFinite(penteDeg) ? penteDeg : PENTE_HAUTEURS_PLEINES_DEG;
  const k = Math.max(ECRASEMENT_PLAN, Math.min(1, p / PENTE_HAUTEURS_PLEINES_DEG));
  return k >= 1 ? new THREE.Matrix4() : new THREE.Matrix4().makeScale(1, 1, k);
}
