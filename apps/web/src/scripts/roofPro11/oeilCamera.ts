// ACAL1984 (suite) — l'ŒIL de la caméra de la couche MapLibre. La couche reçoit UNE matrice modèle → écran (projection
// de la carte × matrice du modèle) ; posée telle quelle sur une THREE.Camera IDENTITÉ, le shader croit l'œil à l'origine
// de la scène (sous le toit) : vues rasantes, Fresnel à 1 (verre éteint), diffus assombri en tache au-dessus de l'origine.
// `poserOeil` retrouve l'œil RÉEL (le point que la matrice envoie à w = 0, x = y = 0) et répartit la même matrice en
// vue (translation vers l'œil) × projection : l'image est identique au pixel près, l'éclairage devient juste.
import * as THREE from 'three';

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
