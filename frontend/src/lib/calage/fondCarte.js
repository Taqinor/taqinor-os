// ACAL203 — LE FOND DE CARTE des écrans de calage (photo de site du calepinage,
// photo de toit de la visite) : UN seul module, jusque-là deux copies
// (`PhotoSiteCalage.jsx`, `CalageToitPage.jsx`) qui demandaient le zoom 20 à
// une couche OSM qui n'a PAS de tuile au-delà de 19 (le serveur répond 400).
//
// RÈGLE : les tuiles ne sont demandées qu'à leur zoom NATIF (`maxNativeZoom`
// 19) ; au-delà, Leaflet agrandit la tuile 19 — aucune requête en 400.
//
// IMAGERIE SOCIÉTÉ : quand la société a réglé son fournisseur d'imagerie
// (`calepinage.selectors.imagerie_site`, servi par `GET calepinage/parametres/`
// section `imagerie`), la tuile de CE fournisseur remplace OSM — seulement si
// on sait la construire ET si la mention légale SAISIE (`attribution`) est là :
// un fournisseur exigeant sa mention n'est jamais affiché sans elle. Tout le
// reste (non réglé, fournisseur à clé, mention absente) garde OSM : le
// comportement d'aujourd'hui, strictement inchangé.

export const ZOOM_INITIAL = 19
export const MAX_NATIVE_ZOOM = 19
export const MAX_ZOOM = 21

const OSM = {
  url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
  attribution: '&copy; OpenStreetMap',
}

// Fournisseurs dont la tuile se construit SANS clé secrète. IGN BD ORTHO® :
// WMTS public de la Géoplateforme (option France du serveur, services/site.py).
const TUILES_PAR_FOURNISSEUR = {
  ign_bd_ortho: {
    url: 'https://data.geopf.fr/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0'
      + '&LAYER=ORTHOIMAGERY.ORTHOPHOTOS&STYLE=normal&FORMAT=image/jpeg'
      + '&TILEMATRIXSET=PM&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}',
  },
}

/** `{url, attribution}` de la tuile à poser pour la section `imagerie` donnée. */
export function tuileDeFond(imagerie) {
  const section = imagerie && typeof imagerie === 'object' ? imagerie : {}
  const actif = section.fournisseur_imagerie
    || (Array.isArray(section.fournisseurs_autorises)
      ? section.fournisseurs_autorises[0] : null)
  const tuile = actif ? TUILES_PAR_FOURNISSEUR[actif] : null
  const attribution = typeof section.attribution === 'string' ? section.attribution.trim() : ''
  if (tuile && attribution) return { url: tuile.url, attribution }
  return OSM
}

/** Pose le fond de carte sur `map` (instance Leaflet) ; rend la couche. */
export function poserFondCarte(L, map, imagerie = null) {
  const { url, attribution } = tuileDeFond(imagerie)
  return L.tileLayer(url, {
    attribution,
    maxZoom: MAX_ZOOM,
    maxNativeZoom: MAX_NATIVE_ZOOM,
  }).addTo(map)
}
