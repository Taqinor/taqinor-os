// ENF19 — briques Three.js communes à roof-tool-pro.ts et roofPro11/scene3d.ts :
// jusque-là recopiées à l'identique. Aucun changement de comportement.
import * as THREE from 'three';
import { DEG2RAD } from './constants';

const AXIS_X = new THREE.Vector3(1, 0, 0);
const AXIS_Z = new THREE.Vector3(0, 0, 1);

/** Fabrique la matrice monde d'une instance : translation (px,py,pz) · rotation Z puis X. */
export function makeCompose(): (px: number, py: number, pz: number, rotZ: number, rotX: number) => THREE.Matrix4 {
  const _q = new THREE.Quaternion();
  const _qz = new THREE.Quaternion();
  const _qx = new THREE.Quaternion();
  const _scl = new THREE.Vector3(1, 1, 1);
  return (px: number, py: number, pz: number, rotZ: number, rotX: number): THREE.Matrix4 => {
    _qz.setFromAxisAngle(AXIS_Z, rotZ);
    _qx.setFromAxisAngle(AXIS_X, rotX);
    _q.copy(_qz).multiply(_qx);
    return new THREE.Matrix4().compose(new THREE.Vector3(px, py, pz), _q, _scl);
  };
}

/** Options de rendu communes (ombres douces, sRGB, tone mapping ACES). */
export function configureShadowRenderer(renderer: THREE.WebGLRenderer): void {
  renderer.autoClear = false;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;
}

/** Boîte englobante XY d'un ou plusieurs anneaux. */
export function ringsBBox(rings: [number, number][][]): { minX: number; minY: number; maxX: number; maxY: number } {
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  for (const r of rings) {
    for (const [x, y] of r) {
      minX = Math.min(minX, x);
      minY = Math.min(minY, y);
      maxX = Math.max(maxX, x);
      maxY = Math.max(maxY, y);
    }
  }
  return { minX, minY, maxX, maxY };
}

/** Cadre la caméra d'ombre du soleil sur une emprise de demi-côté `span`. */
export function fitShadowCamera(sun: THREE.DirectionalLight, span: number, far: number): void {
  const sc = sun.shadow.camera as THREE.OrthographicCamera;
  sc.left = -span;
  sc.right = span;
  sc.top = span;
  sc.bottom = -span;
  sc.near = 0.5;
  sc.far = far;
  sc.updateProjectionMatrix();
}

/** W87 — élévation d'AFFICHAGE minimale du soleil (°) : près du lever ou du coucher la scène reste éclairée (ombres
 *  longues mais lisibles, jamais noire). C'est aussi l'élévation la plus basse que la lecture de la journée atteint. */
export const ELEVATION_AFFICHAGE_MIN_DEG = 6;

/** Où poser le soleil : centre et hauteur de visée (repère ENU de la scène, m), demi-côté du cadre d'ombre, latitude. */
export interface CadreSoleil { cx: number; cy: number; z: number; span: number; lat: number }

/**
 * W87 — le VRAI soleil (azimut et élévation astronomiques de `sunDirection`, à l'heure solaire et au jour choisis) posé
 * sur la lumière directionnelle : azimut dans le repère ENU de la scène (0 = Nord, sens horaire vers l'Est, même
 * convention que `pack.azimuthDeg`), élévation jamais sous `ELEVATION_AFFICHAGE_MIN_DEG`, caméra d'ombre recadrée.
 * Lot 8 — extrait tel quel de `scene3d.ts::renderScene`, pour qu'un pas de soleil ne reconstruise AUCUN maillage.
 */
export function placerSoleilScene(sun: THREE.DirectionalLight, cadre: CadreSoleil, dir: { azimuthDeg: number; elevationDeg: number }): void {
  const azR = dir.azimuthDeg * DEG2RAD;
  const elR = Math.max(ELEVATION_AFFICHAGE_MIN_DEG, dir.elevationDeg) * DEG2RAD;
  const dist = cadre.span * 2.5;
  sun.target.position.set(cadre.cx, cadre.cy, cadre.z);
  sun.position.set(cadre.cx + Math.sin(azR) * Math.cos(elR) * dist, cadre.cy + Math.cos(azR) * Math.cos(elR) * dist, cadre.z + Math.sin(elR) * dist);
  fitShadowCamera(sun, cadre.span, dist * 2);
}
