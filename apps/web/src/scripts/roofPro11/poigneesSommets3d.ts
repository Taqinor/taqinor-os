/* ACAL1185 — poignées des coins du tracé POSÉES AU HAUT DES MURS en vue 3D inclinée (au sol, elles se cachent
   sous le volume du bâtiment). La scène les pose et masque les cercles `rp9-pts` du sol tant que la vue reste
   inclinée ; en vue de dessus rien ne change. Aucune hauteur supposée : celle que `hauteurExtrusion` sert déjà. */
import * as THREE from 'three';
import type { Map as CarteMapLibre } from 'maplibre-gl';
import { DEG2M, DEG2RAD } from './constants';
import { enPresentation, surPresentation } from './presentationCarte'; // H6 — vue client : aucune poignée

export interface PoigneeSommet { idx: number; x: number; y: number; z: number }
export interface PoigneeEcran { idx: number; x: number; y: number }

/** Les coins du tracé en repère ENU de la scène (mètres autour de `origine`), à la hauteur `hauteurM`. */
export function positionsPoignees(sommets: readonly (readonly [number, number])[], origine: readonly [number, number], hauteurM: number): PoigneeSommet[] {
  const cosLat = Math.cos(origine[1] * DEG2RAD);
  return sommets.map(([lng, lat], idx) => ({ idx, x: (lng - origine[0]) * DEG2M * cosLat, y: (lat - origine[1]) * DEG2M, z: hauteurM }));
}

/** Position écran (px CSS, origine en haut à gauche) de chaque poignée ; `m` = matrice colonne-major ENU → clip. */
export function projeterPoignees(poignees: readonly PoigneeSommet[], m: ArrayLike<number>, largeur: number, hauteur: number): PoigneeEcran[] {
  return poignees.flatMap((p) => {
    const w = m[3] * p.x + m[7] * p.y + m[11] * p.z + m[15];
    if (!(w > 0)) return []; // derrière la caméra
    const nx = (m[0] * p.x + m[4] * p.y + m[8] * p.z + m[12]) / w;
    const ny = (m[1] * p.x + m[5] * p.y + m[9] * p.z + m[13]) / w;
    return [{ idx: p.idx, x: (nx * 0.5 + 0.5) * largeur, y: (0.5 - ny * 0.5) * hauteur }];
  });
}

/** Le coin dont la poignée est à moins de `rayonPx` du point écran (le plus proche), sinon null. */
export function coinLePlusProche(ecran: readonly PoigneeEcran[], pt: { x: number; y: number }, rayonPx: number): number | null {
  let meilleur: number | null = null;
  let dMin = rayonPx;
  for (const p of ecran) {
    const d = Math.hypot(p.x - pt.x, p.y - pt.y);
    if (d <= dMin) { dMin = d; meilleur = p.idx; }
  }
  return meilleur;
}

/** L'état des poignées 3D d'une carte : `poser` à chaque rendu de scène, `ecran` pour la saisie, `masquer` pour les captures. */
export function creerPoignees3d(map: CarteMapLibre) {
  let poignees: PoigneeSommet[] = [];
  let groupe: THREE.Group | null = null;
  let matrice: ArrayLike<number> | null = null;
  const geo = new THREE.SphereGeometry(0.3, 12, 8);
  const mat = new THREE.MeshBasicMaterial({ color: 0xe8b54a, depthTest: false });
  const incline = () => poignees.length > 0 && (map.getPitch?.() ?? 0) > 0 && !enPresentation(map);
  const maj = () => {
    if (groupe) groupe.visible = incline();
    if (map.getLayer?.('rp9-pts')) map.setLayoutProperty('rp9-pts', 'visibility', incline() || enPresentation(map) ? 'none' : 'visible');
  };
  map.on?.('pitch', maj);
  surPresentation(map, maj);
  return {
    suivre: (m: ArrayLike<number>) => { matrice = m; },
    poser(scene: THREE.Scene, sommets: readonly (readonly [number, number])[], origine: readonly [number, number], hauteurM: number) {
      groupe?.removeFromParent();
      poignees = sommets.length >= 3 ? positionsPoignees(sommets, origine, hauteurM) : [];
      groupe = poignees.length ? new THREE.Group() : null;
      for (const p of poignees) {
        const m = new THREE.Mesh(geo, mat);
        m.position.set(p.x, p.y, p.z);
        m.renderOrder = 10;
        groupe?.add(m);
      }
      if (groupe) scene.add(groupe);
      maj();
    },
    ecran(): PoigneeEcran[] {
      const c = map.getCanvas();
      return incline() && matrice ? projeterPoignees(poignees, matrice, c.clientWidth, c.clientHeight) : [];
    },
    masquer(): () => void {
      const g = groupe;
      if (g) g.visible = false;
      return () => { if (g) g.visible = incline(); };
    },
  };
}
