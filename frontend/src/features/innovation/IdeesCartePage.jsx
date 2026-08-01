import { useEffect, useMemo, useState, lazy, Suspense } from 'react'
import { useNavigate } from 'react-router-dom'
import innovationApi from '../../api/innovationApi'
// VX186 — `MapView` (leaflet) en `lazy` : seul le COMPOSANT porte le poids
// de leaflet (même patron que ``pages/CartePage.jsx``).
import { escapeHtml } from '../../components/MapView'
import { Badge, EmptyState, Spinner } from '../../ui'
import { StatutIdeePill } from './innovationStatus'

const MapView = lazy(() => import('../../components/MapView'))

/* ============================================================================
   NTIDE55 — Carte des idées liées à un chantier (GPS du chantier lié,
   NTIDE14). Réservé au palier admin/responsable (« Affichage admin seul »),
   route elle-même gatée côté serveur (``IdeasSeeAll``) ET côté client (cf.
   module.config.jsx). Cliquer un marqueur ouvre le détail de l'idée
   (drill-down, réutilise ``MapView``/``onMarkerClick``, même composant que
   ``CartePage``/``ParcInstallePage``).
   ========================================================================== */

export default function IdeesCartePage() {
  const navigate = useNavigate()
  const [points, setPoints] = useState([])
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState('')

  useEffect(() => {
    let alive = true
    innovationApi.geolocalisation()
      .then((res) => { if (alive) setPoints(res.data?.results || []) })
      .catch(() => { if (alive) setErr('Carte indisponible.') })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [])

  const markers = useMemo(() => points
    .filter((p) => p.gps_lat != null && p.gps_lng != null)
    .map((p) => ({
      id: p.id,
      lat: p.gps_lat,
      lng: p.gps_lng,
      label: p.titre,
      detail_path: `/innovation/idees/${p.id}`,
      popupHtml: `<div class="mt-1 text-xs text-muted-foreground">${escapeHtml(p.statut_display)}</div>`,
    })), [points])

  const openIdee = (m) => { if (m.detail_path) navigate(m.detail_path) }

  return (
    <div className="page">
      <div className="page-header flex-wrap gap-3">
        <h2>Idées géolocalisées</h2>
        {points.length > 0 && (
          <Badge tone="neutral">{points.length} idée(s) liée(s) à un chantier</Badge>
        )}
      </div>

      {err && <p className="text-destructive">{err}</p>}
      {loading && <p className="page-loading"><Spinner /> Chargement…</p>}

      {!loading && !err && markers.length === 0 && (
        <EmptyState
          title="Aucune idée géolocalisée"
          description="Liez une idée à un chantier (action « Lier ») dont le GPS est renseigné pour la voir apparaître ici."
          className="my-4"
        />
      )}

      {!loading && !err && markers.length > 0 && (
        <Suspense fallback={<p className="page-loading"><Spinner /> Chargement de la carte…</p>}>
          <MapView markers={markers} onMarkerClick={openIdee} />
        </Suspense>
      )}

      {/* Repli accessible/liste, en plus de la carte (même esprit que la
          liste clavier interne de MapView) : chaque idée reste ouvrable
          sans dépendre de la carte. */}
      {!loading && !err && points.length > 0 && (
        <ul className="mt-4 flex flex-col gap-1.5">
          {points.map((p) => (
            <li key={p.id}>
              <button
                type="button"
                className="flex w-full items-center justify-between gap-2 rounded-md px-2 py-1.5 text-left text-sm hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                onClick={() => navigate(`/innovation/idees/${p.id}`)}
              >
                <span className="truncate">{p.titre}</span>
                <StatutIdeePill status={p.statut} />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
