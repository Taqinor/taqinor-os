/* ACAL345 — LES saisies de référence des surfaces de pose (terrain au sol),
   partagées par les tests de `surfacePose.js` (node:test) et de l'écran
   `ModeTerrain.jsx` (vitest) au lieu d'être recopiées dans chacun. Données
   pures : aucun import de framework de test, lisible des deux côtés. */

/** Un champ au sol complet (module 720 Wc, allée laissée au moteur). */
export const SAISIE_SOL = Object.freeze({
  repere: 'TERRAIN',
  label: 'Champ au sol',
  largeurM: '20',
  profondeurM: '10',
  penteTerrainDeg: '3',
  rowAzimuthDeg: '180',
  tiltDeg: '25',
  moduleLongM: '2.278',
  moduleCourtM: '1.134',
  puissanceWc: '720',
  modulesParTable: '2',
  alleeM: '',
})
