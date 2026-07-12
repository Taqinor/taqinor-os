import { useEffect, useMemo, useState, lazy, Suspense } from 'react'
import { useNavigate } from 'react-router-dom'
import reportingApi from '../api/reportingApi'
// VX186 — `MapView` (leaflet, 150,7 Ko/44,4 gzip) en `lazy` : `escapeHtml`
// (fonction pure, utilisée dans le `useMemo` des marqueurs) reste un import
// statique — seul le COMPOSANT porte le poids de leaflet.
import { escapeHtml } from '../components/MapView'
import { Badge } from '../ui/Badge'
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '../ui/Select'
import { EmptyState } from '../ui/EmptyState'
import { Spinner } from '../ui/Spinner'

const MapView = lazy(() => import('../components/MapView'))

// N85 — Vue carte : leads, chantiers, systèmes installés et visites prévues sur
// une carte (Leaflet / OpenStreetMap), filtrables par type ET par statut.
// Cliquer un marqueur ouvre la fiche correspondante. Toutes les données sont
// bornées à la société de l'utilisateur (filtrage serveur).

// VX32 — chaque type porte un `tone` Badge (composants du design system) et
// un `color` en variable CSS de thème (jamais de hex figé) pour l'épingle
// Leaflet — s'adapte donc automatiquement en mode sombre.
const TYPES = [
  { key: 'lead', label: 'Leads', tone: 'info', color: 'var(--info)' },
  { key: 'chantier', label: 'Chantiers', tone: 'warning', color: 'var(--warning)' },
  { key: 'installe', label: 'Systèmes installés', tone: 'success', color: 'var(--success)' },
  { key: 'visite', label: 'Visites prévues', tone: 'primary', color: 'var(--primary)' },
]
const COLOR = Object.fromEntries(TYPES.map((t) => [t.key, t.color]))

export default function CartePage() {
  const navigate = useNavigate()
  const [points, setPoints] = useState([])
  const [counts, setCounts] = useState({})
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState('')
  // Types masqués (clic sur la pastille pour basculer).
  const [hidden, setHidden] = useState(() => new Set())
  // Filtre statut (côté client : la liste des statuts dépend des points reçus).
  const [statut, setStatut] = useState('')

  useEffect(() => {
    let alive = true
    reportingApi.getGeoPoints()
      .then((r) => {
        if (!alive) return
        setPoints(r.data.points || [])
        setCounts(r.data.counts || {})
      })
      .catch(() => { if (alive) setErr('Carte indisponible.') })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [])

  const toggleType = (k) => setHidden((prev) => {
    const next = new Set(prev)
    next.has(k) ? next.delete(k) : next.add(k)
    return next
  })

  // Statuts disponibles (clé → libellé), dérivés des points visibles par type.
  const statutOptions = useMemo(() => {
    const map = new Map()
    points.forEach((p) => {
      if (hidden.has(p.type)) return
      if (p.statut && !map.has(p.statut)) {
        map.set(p.statut, p.statut_label || p.statut)
      }
    })
    return Array.from(map, ([value, label]) => ({ value, label }))
      .sort((a, b) => a.label.localeCompare(b.label, 'fr'))
  }, [points, hidden])

  // Marqueurs visibles, colorés par type, avec un libellé de statut en popup.
  const markers = useMemo(() => points
    .filter((p) => !hidden.has(p.type) && p.lat != null && p.lng != null)
    .filter((p) => !statut || p.statut === statut)
    .map((p) => ({
      id: p.id,
      lat: p.lat,
      lng: p.lng,
      label: p.label,
      color: COLOR[p.type] || '#64748b',
      detail_path: p.detail_path,
      // ERR26 — échapper chaque valeur serveur avant de l'injecter dans le HTML.
      // Classes Tailwind (tokens) plutôt qu'un style inline en hex : le popup
      // Leaflet est du HTML brut hors de l'arbre React, mais partage la même
      // feuille de styles applicative.
      popupHtml: `<div class="mt-1 text-xs text-muted-foreground">`
        + `${escapeHtml(p.type_label)}${p.statut_label ? ' · ' + escapeHtml(p.statut_label) : ''}`
        + (p.date ? ` · ${escapeHtml(p.date)}` : '')
        + `</div>`,
    })), [points, hidden, statut])

  const openRecord = (m) => { if (m.detail_path) navigate(m.detail_path) }

  return (
    <div className="page">
      <div className="page-header flex-wrap gap-3">
        <h2>Carte</h2>
        {counts.total ? (
          <Badge tone="neutral">{counts.total} point(s) géolocalisé(s)</Badge>
        ) : null}
      </div>

      {/* Filtres par type (légende cliquable) + filtre par statut. */}
      <div className="mb-3 flex flex-wrap items-center gap-2">
        {TYPES.map((t) => {
          const off = hidden.has(t.key)
          const n = counts[t.key] || 0
          return (
            <button
              key={t.key}
              type="button"
              onClick={() => toggleType(t.key)}
              title={off ? 'Afficher' : 'Masquer'}
              aria-pressed={!off}
              className="rounded-full focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <Badge tone={off ? 'outline' : t.tone}>
                {t.label}{n ? ` (${n})` : ''}
              </Badge>
            </button>
          )
        })}

        <Select value={statut || '_all'} onValueChange={(v) => setStatut(v === '_all' ? '' : v)}>
          <SelectTrigger aria-label="Filtrer par statut" className="ml-auto w-auto min-w-40">
            <SelectValue placeholder="Tous les statuts" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="_all">Tous les statuts</SelectItem>
            {statutOptions.map((s) => (
              <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {err && <p className="text-destructive">{err}</p>}
      {loading && <p className="page-loading">Chargement…</p>}

      {!loading && !err && markers.length === 0 && (
        // VX40 — pictogramme solaire illustré (l'un des 4-5 écrans les plus vus).
        <EmptyState
          illustrated
          title="Aucun enregistrement géolocalisé"
          description="Ajoutez les coordonnées GPS sur les leads et les chantiers pour les voir ici."
          className="my-4"
        />
      )}

      <Suspense fallback={<p className="page-loading"><Spinner /> Chargement de la carte…</p>}>
        <MapView markers={markers} onMarkerClick={openRecord} />
      </Suspense>
    </div>
  )
}
