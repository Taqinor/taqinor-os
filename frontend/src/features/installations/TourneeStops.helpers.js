// ENF22 — helpers extraits de TourneeStops.jsx (react-refresh/only-export-components) : le fichier composant n'exporte plus que des composants.

export // Un arrêt géolocalisable ? (le GPS du chantier est nullable côté serveur)
const aGps = (s) => s?.gps_lat != null && s?.gps_lng != null

// Helper PUR co-localise avec le composant qui l'utilise ; l'extraire casserait
// les tests sonde qui epinglent le texte source de CE fichier. Regle HMR de dev.
export const stopLabel = (stop, rang) => (
  `${rang}. ${stop?.client_nom || stop?.installation_reference || `#${stop?.id}`}`
)

// Marqueurs numérotés DANS L'ORDRE de la tournée (l'ordre serveur, plus proche
// voisin) — les arrêts sans GPS sont simplement absents de la carte, jamais
// posés à une position inventée ; ils restent visibles dans la liste.
// Helper PUR co-localise avec le composant qui l'utilise ; l'extraire casserait
// les tests sonde qui epinglent le texte source de CE fichier. Regle HMR de dev.
export function tourneeMarkers(stops) {
  return (stops ?? []).map((stop, i) => ({ stop, rang: i + 1 }))
    .filter(({ stop }) => aGps(stop))
    .map(({ stop, rang }) => ({
      id: stop.id,
      lat: Number(stop.gps_lat),
      lng: Number(stop.gps_lng),
      badge: rang,
      label: stopLabel(stop, rang),
      color: '#2563eb',
    }))
}

// Helper PUR co-localise avec le composant qui l'utilise ; l'extraire casserait
// les tests sonde qui epinglent le texte source de CE fichier. Regle HMR de dev.
export const tourneePath = (stops) => tourneeMarkers(stops).map((m) => [m.lat, m.lng])
