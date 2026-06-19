import { useEffect, useRef } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

// N85 — Composant carte réutilisable (Leaflet + tuiles OpenStreetMap, sans clé
// API). Pilotage IMPÉRATIF de Leaflet (pas de react-leaflet) pour éviter tout
// conflit de pair React. À réutiliser partout où une carte est nécessaire.
//
// Props :
//   markers       : [{ id, lat, lng, label, color?, popupHtml? }]
//   onMarkerClick : (marker) => void   — clic sur un marqueur
//   center        : [lat, lng]         — centre par défaut (défaut : Maroc)
//   zoom          : number             — zoom par défaut
//   height        : CSS height (défaut 70vh)
//   fitToMarkers  : bool — recadre la vue sur l'ensemble des marqueurs

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

const escapeHtml = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => (
  { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
))

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
  const clickRef = useRef(onMarkerClick)

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
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
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
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

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
      marker.bindPopup(
        `<div class="mapview-popup"><strong>${title}</strong>${extra}</div>`)
      marker.on('click', () => {
        if (clickRef.current) clickRef.current(m)
      })
      marker.addTo(layer)
      latlngs.push([m.lat, m.lng])
    })
    if (fitToMarkers && latlngs.length > 0) {
      map.fitBounds(L.latLngBounds(latlngs), {
        padding: [40, 40], maxZoom: 13,
      })
    }
  }, [markers, fitToMarkers])

  return (
    <div
      ref={containerRef}
      className="mapview-container"
      style={{ height, width: '100%', borderRadius: 8, overflow: 'hidden' }}
    />
  )
}
