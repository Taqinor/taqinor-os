// ACAL435 — quatre vues de caméra prêtes (Dessus, Sud, 3/4, Face aux panneaux).
// `cibleVue` est PURE (aucune valeur de données) ; `appliquerVue` pose la cible sur la carte,
// en 600 ms, ou instantanément sous `prefers-reduced-motion`.
import { PITCH_VIEW } from './constants';

export type NomVue = 'dessus' | 'sud' | 'trois-quarts' | 'face-panneaux';
export const CAP_TROIS_QUARTS_DEG = 45;
export const DUREE_VUE_MS = 600;

export function cibleVue(nom: NomVue, azimutPanDeg: number): { pitch: number; bearing: number } {
  switch (nom) {
    case 'dessus':
      return { pitch: 0, bearing: 0 };
    case 'sud':
      return { pitch: PITCH_VIEW, bearing: 0 };
    case 'trois-quarts':
      return { pitch: PITCH_VIEW, bearing: CAP_TROIS_QUARTS_DEG };
    case 'face-panneaux':
      return { pitch: PITCH_VIEW, bearing: (((azimutPanDeg + 180) % 360) + 360) % 360 };
  }
}

interface CarteCamera {
  jumpTo(o: { pitch: number; bearing: number }): unknown;
  easeTo(o: { pitch: number; bearing: number; duration: number; essential?: boolean }): unknown;
}

export function appliquerVue(map: CarteCamera, nom: NomVue, azimutPanDeg: number, reducedMotion: boolean): void {
  const cible = cibleVue(nom, azimutPanDeg);
  if (reducedMotion) map.jumpTo(cible);
  else map.easeTo({ ...cible, duration: DUREE_VUE_MS, essential: true });
}
