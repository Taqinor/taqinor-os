// W90 (déplacé tel quel, ACAL1839) — la JUPE d'un pan en pente : pour chaque arête (a→b) de l'anneau, un quadrilatère
// vertical du haut du mur (z = 0, repère local) jusqu'au dessous de la dalle inclinée (`hauteurDalle(x, y)`). Le pan aval
// n'a qu'un mince mur, l'amont monte en triangle : lecture « pignon/croupe » fermée. Servie au pan actif, aux pans voisins
// et, depuis ACAL1839, aux pans NUS (sans panneaux) de l'atelier ERP.
import * as THREE from 'three';

export function geometrieJupe(ring: readonly (readonly [number, number])[], hauteurDalle: (x: number, y: number) => number): THREE.BufferGeometry {
  const n = ring.length;
  const positions: number[] = [];
  for (let i = 0; i < n; i++) {
    const [ax, ay] = ring[i];
    const [bx, by] = ring[(i + 1) % n];
    const za = hauteurDalle(ax, ay);
    const zb = hauteurDalle(bx, by);
    // Deux triangles (a-bas, b-bas, b-haut) + (a-bas, b-haut, a-haut) ; normales recalculées, matériau double face.
    positions.push(ax, ay, 0, bx, by, 0, bx, by, zb);
    positions.push(ax, ay, 0, bx, by, zb, ax, ay, za);
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(positions), 3));
  geo.computeVertexNormals();
  return geo;
}
