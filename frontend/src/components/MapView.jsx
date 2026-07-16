import { useEffect, useRef } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { useTheme } from '../design/theme-context'

// N85 — Composant carte réutilisable (Leaflet + tuiles OpenStreetMap, sans clé
// API). Pilotage IMPÉRATIF de Leaflet (pas de react-leaflet) pour éviter tout
// conflit de pair React. À réutiliser partout où une carte est nécessaire.
//
// Props :
//   markers       : [{ id, lat, lng, label, color?, popupHtml? }]
//   onMarkerClick : (marker) => void   — clic sur un marqueur OU sur le bouton
//                   « Ouvrir la fiche » du popup (VX32, affiché seulement si fourni)
//   center        : [lat, lng]         — centre par défaut (défaut : Maroc)
//   zoom          : number             — zoom par défaut
//   height        : CSS height (défaut 70vh)
//   fitToMarkers  : bool — recadre la vue sur l'ensemble des marqueurs
//
// VX32 — tuiles OSM assombries en mode sombre via filtre CSS (lit le thème
// résolu depuis <ThemeProvider>) : pas de fond blanc figé la nuit.

// Centre par défaut : le Maroc (les données métier sont marocaines).
const DEFAULT_CENTER = [31.7917, -7.0926]
const DEFAULT_ZOOM = 6

// Marqueur coloré en SVG (divIcon) — évite de dépendre des images d'icône
// Leaflet (chemins cassés par les bundlers) et permet une couleur par type.
function coloredIcon(color = '#2563eb') {
  const html = `
    <svg width="26" height="38" viewBox="0 0 26 38" xmlns="http://www.w3.org/2000/svg">
      <path d="M13 0C5.82 0 0 5.82 0 13c0 9.25 13 25 13 25s13-15.75 13-25C26 5.82 20.18 0 13 0z"
            fill="${color}" stroke="#ffffff" stroke-width="2"/>
      <circle cx="13" cy="13" r="5" fill="#ffffff"/>
    </svg>`
  return L.divIcon({
    html,
    className: 'mapview-pin',
    iconSize: [26, 38],
    iconAnchor: [13, 38],
    popupAnchor: [0, -34],
  })
}

// ERR26 — Échappement HTML de TOUTE valeur issue du serveur avant de la
// concaténer dans le `popupHtml` du marqueur (un nom de client/lead/statut
// contenant du markup exécuterait sinon du XSS stocké à l'ouverture du popup).
// Exporté pour que les appelants (CartePage, ParcInstallePage) réutilisent le
// même helper plutôt que de bâtir du HTML brut.
// eslint-disable-next-line react-refresh/only-export-components -- helper pur partagé avec les appelants, pas un composant
export const escapeHtml = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => (
  { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
))

// VX32 — filtre CSS sur les tuiles OSM en mode sombre (aucune tuile "dark"
// dédiée nécessaire : invert() + hue-rotate() est le pattern standard, zéro
// dépendance). Laisse les icônes de marqueurs (SVG, hors du tileLayer) intactes.
const DARK_TILE_FILTER = 'invert(1) hue-rotate(180deg) brightness(0.95) contrast(0.9)'

export default function MapView({
  markers = [],
  onMarkerClick,
  center = DEFAULT_CENTER,
  zoom = DEFAULT_ZOOM,
  height = '70vh',
  fitToMarkers = true,
}) {
  const containerRef = useRef(null)
  const mapRef = useRef(null)
  const layerRef = useRef(null)
  const tileLayerRef = useRef(null)
  const clickRef = useRef(onMarkerClick)
  const { resolvedTheme } = useTheme()

  // Garde le gestionnaire de clic à jour sans recréer les marqueurs.
  useEffect(() => { clickRef.current = onMarkerClick }, [onMarkerClick])

  // Initialise la carte une seule fois.
  useEffect(() => {
    if (mapRef.current || !containerRef.current) return
    const map = L.map(containerRef.current, {
      center,
      zoom,
      scrollWheelZoom: true,
    })
    tileLayerRef.current = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      maxZoom: 19,
    }).addTo(map)
    layerRef.current = L.layerGroup().addTo(map)
    mapRef.current = map
    return () => {
      map.remove()
      mapRef.current = null
      layerRef.current = null
      tileLayerRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // VX32 — mode sombre : filtre CSS sur les tuiles (pas de fond blanc figé).
  useEffect(() => {
    const tileLayer = tileLayerRef.current
    if (!tileLayer) return
    const pane = tileLayer.getPane?.()
    if (pane) pane.style.filter = resolvedTheme === 'dark' ? DARK_TILE_FILTER : ''
  }, [resolvedTheme, markers])

  // (Re)dessine les marqueurs à chaque changement de la liste.
  useEffect(() => {
    const map = mapRef.current
    const layer = layerRef.current
    if (!map || !layer) return
    layer.clearLayers()
    const latlngs = []
    markers.forEach((m) => {
      if (m.lat == null || m.lng == null) return
      const marker = L.marker([m.lat, m.lng], { icon: coloredIcon(m.color) })
      const title = escapeHtml(m.label)
      const extra = m.popupHtml || ''
      // VX32 — bouton « Ouvrir la fiche » dans le popup (même appel que le clic
      // sur le marqueur) : le contenu du popup reste du HTML brut (Leaflet), le
      // clic est câblé après l'ouverture via l'évènement `popupopen` ci-dessous.
      const openBtn = onMarkerClick
        ? '<button type="button" data-mapview-open="1" '
          + 'class="mt-2 inline-flex h-[var(--control-h-sm)] items-center justify-center '
          + 'rounded-md bg-primary px-3 text-xs font-medium text-primary-foreground '
          + 'shadow-ui-xs hover:bg-primary/90">Ouvrir la fiche</button>'
        : ''
      marker.bindPopup(
        `<div class="mapview-popup"><strong>${title}</strong>${extra}${openBtn}</div>`)
      marker.on('click', () => {
        if (clickRef.current) clickRef.current(m)
      })
      marker.on('popupopen', (e) => {
        const btn = e.popup.getElement()?.querySelector('[data-mapview-open]')
        if (btn) {
          btn.onclick = () => { if (clickRef.current) clickRef.current(m) }
        }
      })
      marker.addTo(layer)
      latlngs.push([m.lat, m.lng])
    })
    if (fitToMarkers && latlngs.length > 0) {
      map.fitBounds(L.latLngBounds(latlngs), {
        padding: [40, 40], maxZoom: 13,
      })
    }
  }, [markers, fitToMarkers, onMarkerClick])

  // VX195 — la carte Leaflet est manipulée en impératif (pas de rôle/focus
  // natif sur les marqueurs) : un technicien au clavier ou avec un lecteur
  // d'écran n'a aucun moyen d'atteindre les points géolocalisés. On ajoute
  // (1) role="application" + aria-label FR annonçant le nombre de points sur
  // le conteneur carte, et (2) une liste de boutons PARALLÈLE (repliable via
  // <details>/<summary> natifs) où chaque marqueur devient un `<button>`
  // focalisable qui appelle le même `onMarkerClick` — sans dépendance ni
  // changement du pilotage impératif de Leaflet.
  const pointCount = markers.length
  const mapLabel = `Carte, ${pointCount} point${pointCount !== 1 ? 's' : ''}`

  return (
    <div>
      <div
        ref={containerRef}
        className="mapview-container"
        role="application"
        aria-label={mapLabel}
        style={{ height, width: '100%', borderRadius: 8, overflow: 'hidden' }}
      />
      {pointCount > 0 && (
        <details className="mapview-keyboard-list mt-2">
          <summary className="cursor-pointer text-sm text-muted-foreground">
            Liste des points de la carte (accès clavier)
          </summary>
          <ul className="mt-1 flex flex-col gap-1" aria-label={mapLabel}>
            {markers.map((m) => (
              <li key={m.id}>
                <button
                  type="button"
                  className="w-full rounded-md px-2 py-1 text-left text-sm hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  onClick={() => { if (onMarkerClick) onMarkerClick(m) }}
                >
                  {m.label}
                </button>
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  )
}
