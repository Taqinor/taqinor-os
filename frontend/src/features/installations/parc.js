// Parc installé (N8) — logique pure (testable hors React) : bandes de
// puissance, construction des paramètres de requête, lien carte, et sélection
// des systèmes géolocalisés.

export const KWC_BANDS = [
  { value: '', label: 'Toutes puissances' },
  { value: '0-3', label: '≤ 3 kWc', min: '', max: '3' },
  { value: '3-9', label: '3 – 9 kWc', min: '3', max: '9' },
  { value: '9-36', label: '9 – 36 kWc', min: '9', max: '36' },
  { value: '36+', label: '> 36 kWc', min: '36', max: '' },
]

export const TYPE_LABELS = {
  residentiel: 'Résidentiel',
  industriel: 'Industriel / Commercial',
  agricole: 'Agricole (pompage)',
}

export const EMPTY_PARC_FILTERS = {
  q: '', ville: '', marque: '', type_installation: '', annee: '', band: '',
}

// Construit les query params backend depuis l'état des filtres. La bande kWc se
// traduit en kwc_min / kwc_max (les bornes vides sont omises).
export function buildParcParams(filters) {
  const band = KWC_BANDS.find((b) => b.value === filters.band)
  return {
    ...(filters.q?.trim() ? { search: filters.q.trim() } : {}),
    ...(filters.ville?.trim() ? { ville: filters.ville.trim() } : {}),
    ...(filters.marque?.trim() ? { marque: filters.marque.trim() } : {}),
    ...(filters.type_installation
      ? { type_installation: filters.type_installation } : {}),
    ...(filters.annee?.trim() ? { annee: filters.annee.trim() } : {}),
    ...(band && band.min ? { kwc_min: band.min } : {}),
    ...(band && band.max ? { kwc_max: band.max } : {}),
  }
}

// Lien OpenStreetMap d'un point (approche carte légère, sans dépendance carto).
export function osmLink(lat, lng) {
  return `https://www.openstreetmap.org/?mlat=${lat}&mlon=${lng}#map=17/${lat}/${lng}`
}

// Systèmes géolocalisés (coordonnées GPS présentes) pour la vue carte.
export function geolocated(rows) {
  return (rows ?? []).filter(
    (r) => r.gps_lat != null && r.gps_lng != null)
}

export function formatKwc(v) {
  return v == null || v === '' ? '—' : `${Number(v).toLocaleString('fr-FR')} kWc`
}
