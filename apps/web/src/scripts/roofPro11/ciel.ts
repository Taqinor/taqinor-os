/**
 * ACAL431 — un ciel qui suit la position du soleil (`map.setSky`), visible quand
 * la carte est inclinée. Pur rendu : rien n'est enregistré, aucune animation.
 * Les teintes sont des constantes d'APPARENCE nommées, jamais une donnée.
 */
import type { Map as MapLibreMap } from 'maplibre-gl';
import { presentationClient } from './jeuPresentation';

/** Le ciel suit-il le soleil ? L'atelier oui ; la visionneuse lecture seule seulement sur un lien de confiance (lot 8). */
export function cielSuitLeSoleil(readOnly: boolean, opts: Parameters<typeof presentationClient>[0]): boolean {
  return !readOnly || presentationClient(opts);
}

export interface CouleursCiel { skyColor: string; horizonColor: string; fogColor: string }

// Teintes d'apparence (nuit / horizon chaud / plein jour), du zénith vers l'horizon.
const NUIT: CouleursCiel = { skyColor: '#0b1226', horizonColor: '#1c2440', fogColor: '#141b33' };
const CHAUD: CouleursCiel = { skyColor: '#6f8fc4', horizonColor: '#f2a65a', fogColor: '#e8b98a' };
const JOUR: CouleursCiel = { skyColor: '#5ea6ec', horizonColor: '#cfe6fb', fogColor: '#e4f0fb' };
const ELEV_CHAUD = 8; // ° : au-dessus, le ciel a fini de se refroidir vers le bleu du jour
const ELEV_JOUR = 30;

const canal = (hex: string, i: number) => parseInt(hex.slice(1 + 2 * i, 3 + 2 * i), 16);
const melange = (a: string, b: string, t: number) => '#' + [0, 1, 2]
  .map((i) => Math.round(canal(a, i) + (canal(b, i) - canal(a, i)) * t).toString(16).padStart(2, '0'))
  .join('');
const entre = (a: CouleursCiel, b: CouleursCiel, t: number): CouleursCiel => ({
  skyColor: melange(a.skyColor, b.skyColor, t),
  horizonColor: melange(a.horizonColor, b.horizonColor, t),
  fogColor: melange(a.fogColor, b.fogColor, t),
});

/** Couleurs du ciel pour une élévation solaire (°) : continues, ≤ 0 sombre. */
export function couleursCiel(elevationDeg: number): CouleursCiel {
  if (!(elevationDeg > 0)) return NUIT;
  if (elevationDeg < ELEV_CHAUD) return entre(NUIT, CHAUD, elevationDeg / ELEV_CHAUD);
  if (elevationDeg < ELEV_JOUR) return entre(CHAUD, JOUR, (elevationDeg - ELEV_CHAUD) / (ELEV_JOUR - ELEV_CHAUD));
  return JOUR;
}

/** Pose le ciel sur la carte ; bas de gamme ou carte sans `setSky` : rien. */
export function appliquerCiel(map: MapLibreMap, elevationDeg: number, lowEnd: boolean): void {
  if (lowEnd || typeof map.setSky !== 'function') return;
  const c = couleursCiel(elevationDeg);
  map.setSky({ 'sky-color': c.skyColor, 'horizon-color': c.horizonColor, 'fog-color': c.fogColor });
}
