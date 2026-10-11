// ENF22 — helpers extraits de PhotoSiteCalage.jsx (react-refresh/only-export-components) : le fichier composant n'exporte plus que des composants.

export const DEFAULT_CENTER = [31.7917, -7.0926]

// Maroc — repli si rien n'est connu.
const DELTA = 0.00012

/**
 * Les 4 positions `[lat, lng]` de départ des poignées : celles d'un calage
 * déjà enregistré (relecture EXACTE, jamais recalculée), sinon un petit carré
 * autour du `centre` donné. Fonction PURE — testable sans monter la carte.
 */
export function positionsInitiales(calageExistant, centre) {
  const coins = calageExistant?.coins
  if (Array.isArray(coins) && coins.length === 4) return coins
  const [lat, lng] = centre ?? DEFAULT_CENTER
  return [
    [lat + DELTA, lng - DELTA],
    [lat + DELTA, lng + DELTA],
    [lat - DELTA, lng + DELTA],
    [lat - DELTA, lng - DELTA],
  ]
}

/** Les 4 marqueurs Leaflet → `[[lat, lng] × 4]`, dans leur ordre de pose. */
export function coinsDepuisMarqueurs(marqueurs) {
  return marqueurs.map((m) => {
    const ll = m.getLatLng()
    return [ll.lat, ll.lng]
  })
}
