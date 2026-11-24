// ACAL1820 — la BOÎTE d'un obstacle de toiture (zone active et zones voisines : une définition). Volume semi-transparent
// à la vraie taille, arêtes visibles. Dans l'atelier ERP (`ombres`) : posée SUR la dalle (un pan en pente la relève ;
// elle était enfouie sous le plan incliné) et elle PORTE et REÇOIT les ombres du soleil affiché (LANGAGE.md § 4 :
// « sur la carte, chaque objet porte l'ombre du soleil affiché »). Site public : la boîte d'avant, inchangée.
import * as THREE from 'three';
import { OBSTACLE_BOX_H_M } from './constants';

export interface PoseObstacle {
  /** Centre de l'obstacle dans le repère de la scène (m). */
  x: number;
  y: number;
  /** Hauteur de la face haute du mur (m) — l'assise d'avant. */
  murM: number;
  /** Dessus de la dalle au centre (m), quand l'hôte la connaît (pan en pente). */
  dessusDalleM?: number | null;
  teinte: number;
  opacite: number;
  opaciteAretes?: number;
  /** Atelier ERP : assise sur la dalle + ombres portées et reçues. */
  ombres: boolean;
}

/** La boîte (et ses arêtes) d'un obstacle `{widthM, lengthM, heightM?}`. Hauteur SAISIE, sinon le repli visuel. */
export function boiteObstacle(o: { widthM: number; lengthM: number; heightM?: number | null }, p: PoseObstacle): THREE.Mesh {
  const h = o.heightM ?? OBSTACLE_BOX_H_M;
  const geo = new THREE.BoxGeometry(o.widthM, o.lengthM, h);
  const mat = new THREE.MeshStandardMaterial({ color: p.teinte, metalness: 0.1, roughness: 0.7, transparent: true, opacity: p.opacite, depthWrite: false });
  const mesh = new THREE.Mesh(geo, mat);
  const assise = p.ombres && Number.isFinite(p.dessusDalleM) ? Math.max(p.murM, p.dessusDalleM as number) : p.murM;
  mesh.position.set(p.x, p.y, assise + h / 2 + 0.05);
  mesh.renderOrder = 3;
  mesh.castShadow = p.ombres;
  mesh.receiveShadow = p.ombres;
  mesh.add(new THREE.LineSegments(new THREE.EdgesGeometry(geo), new THREE.LineBasicMaterial({ color: p.teinte, transparent: true, opacity: p.opaciteAretes ?? 0.95 })));
  return mesh;
}
