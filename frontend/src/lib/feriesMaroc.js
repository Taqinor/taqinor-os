/* ============================================================================
   CAD42 — les 9 jours fériés FIXES marocains, côté écran.
   ----------------------------------------------------------------------------
   Ce sont les SEULES dates pour lesquelles « Récurrent chaque année » a un
   sens : les fêtes religieuses (Aïd al-Fitr, Aïd al-Adha, Nouvel An hégirien,
   Aïd al-Mawlid) suivent le calendrier lunaire et tombent un jour grégorien
   différent chaque année. Cocher « Récurrent » sur un Aïd le fige pour
   toujours — l'écran Paramètres → Notifications avertit avant, sans jamais
   refuser la saisie.

   Source officielle : mmsp.gov.ma, calendrier des jours fériés.
   Module à part (et non dans le composant) pour que le rechargement à chaud
   de Vite continue de fonctionner : un fichier d'écran n'exporte que des
   composants.
   ========================================================================== */

/** Les 9 fériés fixes, en `[mois, jour]`. */
export const FERIES_FIXES_MA = [
  [1, 1],    // Jour de l'An
  [1, 11],   // Manifeste de l'Indépendance
  [5, 1],    // Fête du Travail
  [7, 30],   // Fête du Trône
  [8, 14],   // Oued Ed-Dahab
  [8, 20],   // Révolution du Roi et du Peuple
  [8, 21],   // Fête de la Jeunesse
  [11, 6],   // Marche Verte
  [11, 18],  // Fête de l'Indépendance
]

/** Vrai si la date ISO `AAAA-MM-JJ` est l'un des 9 fériés fixes marocains. */
export function estFerieFixeMa(iso) {
  const bouts = String(iso || '').split('-')
  if (bouts.length !== 3) return false
  const mois = Number(bouts[1])
  const jour = Number(bouts[2])
  return FERIES_FIXES_MA.some(([m, j]) => m === mois && j === jour)
}
