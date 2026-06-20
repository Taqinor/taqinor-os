/**
 * Constantes géométriques et de rendu partagées par les modules roofPro11.
 * Extraites de roof-tool-pro11.ts (split modulaire 2026-06-20) — valeurs INCHANGÉES.
 */
export const GOLD = '#f3cc66';
export const MOROCCO_CENTER: [number, number] = [-7.09, 31.79];
export const FLOOR_HEIGHT_M = 3;
export const PITCH_VIEW = 58;
export const DECK_THK = 0.06;
export const FLOORS = 2;
export const OBSTACLE_BOX_H_M = 0.8; // hauteur du volume d'obstacle rendu en 3D
export const OBSTACLE_TAP_PX = 8; // en deçà : un clic/tap, au-delà : un glissé
export const DEG2RAD = Math.PI / 180;
export const WGS84_RADIUS = 6378137;
export const DEG2M = DEG2RAD * WGS84_RADIUS;
