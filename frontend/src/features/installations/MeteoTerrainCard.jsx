// NTMOB21 — Météo terrain sur « Ma journée ».
// Alerte simple et NON bloquante (« Pluie prévue aujourd'hui »), pour aider à
// replanifier une pose de panneaux. Données : `GET installations/meteo/`
// (Open-Meteo, gratuit et sans clé, DÉJÀ intégré côté serveur, cache 1 h par
// coordonnée). Aucun point GPS sur la tournée → le composant ne s'affiche pas ;
// erreur réseau → « Météo indisponible », jamais un toast rouge.
import { useEffect, useState } from 'react'
import { CloudRain } from 'lucide-react'
import installationsApi from '../../api/installationsApi'

export default function MeteoTerrainCard({ stops = [] }) {
  const premier = stops.find((s) => s.site_lat != null && s.site_lng != null)
  const lat = premier?.site_lat
  const lon = premier?.site_lng
  const [meteo, setMeteo] = useState(null)

  useEffect(() => {
    if (lat == null || lon == null) return undefined
    let alive = true
    installationsApi.getMeteoTerrain(lat, lon)
      .then((r) => { if (alive) setMeteo(r.data || null) })
      .catch(() => {
        if (alive) {
          setMeteo({ disponible: false, message: 'Météo indisponible.' })
        }
      })
    return () => { alive = false }
  }, [lat, lon])

  // Rien à dire (pas de point GPS, pas encore chargé, ou météo sans alerte) :
  // on n'occupe pas l'écran du technicien.
  if (!meteo) return null
  const texte = meteo.disponible ? meteo.message : (meteo.message || null)
  if (!texte) return null

  return (
    <div
      role="status"
      data-testid="mj-meteo"
      className="flex items-center gap-2 rounded-md border border-border bg-muted px-3 py-2 text-sm text-muted-foreground"
    >
      <CloudRain className="size-4 shrink-0" aria-hidden="true" />
      <span>{texte}</span>
    </div>
  )
}
