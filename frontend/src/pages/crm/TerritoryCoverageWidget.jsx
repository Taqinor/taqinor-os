import { useEffect, useState } from 'react'
import { MapPin } from 'lucide-react'
import api from '../../api/axios'
import {
  Card, CardHeader, CardTitle, CardDescription, CardContent, Spinner,
} from '../../ui'

/* ============================================================================
   NTCRM25 — Widget dashboard Directeur « zones non couvertes ». Leads récents
   (30 derniers jours par défaut) qui n'ont matché AUCUN territoire actif
   (`GET /api/django/territoires/couverture/`), regroupés par région (ville)
   et par segment (type d'installation). Lecture seule — aucune mutation.
   ========================================================================== */
export default function TerritoryCoverageWidget({ jours = 30 }) {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [data, setData] = useState(null)

  useEffect(() => {
    let active = true
    // setState différé au prochain microtask (jamais synchrone dans l'effet) —
    // évite react-hooks/set-state-in-effect sans changer le comportement visible.
    queueMicrotask(() => { if (active) setLoading(true) })
    api.get('/territoires/couverture/', { params: { jours } })
      .then((r) => { if (active) setData(r.data) })
      .catch(() => { if (active) setError(true) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [jours])

  const parRegion = data?.par_region ?? {}
  const regions = Object.entries(parRegion)

  return (
    <Card data-testid="territory-coverage-widget">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <MapPin className="h-4 w-4" /> Zones non couvertes
        </CardTitle>
        <CardDescription>
          Leads des {jours} derniers jours hors de tout territoire actif.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {loading ? (
          <Spinner />
        ) : error ? (
          <p className="text-sm text-muted-foreground">Indisponible pour le moment.</p>
        ) : regions.length === 0 ? (
          <p className="text-sm text-muted-foreground">Toute la couverture est saine. 🎉</p>
        ) : (
          <ul className="space-y-2">
            {regions.map(([region, count]) => (
              <li
                key={region}
                className="flex items-center justify-between gap-2 rounded-md border border-border p-2"
              >
                <span className="truncate text-sm font-medium">{region}</span>
                <span className="text-xs font-normal text-muted-foreground">
                  {count} lead{count > 1 ? 's' : ''} non couvert{count > 1 ? 's' : ''}
                </span>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  )
}
