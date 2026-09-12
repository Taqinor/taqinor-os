import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ShieldCheck } from 'lucide-react'
import parametresApi from '../../api/parametresApi'
import { Card, CardContent } from '../../ui'

/* ============================================================================
   NTOBS16 — Badge « SLA respecté » auto-calculé (cockpit direction), K51.
   ----------------------------------------------------------------------------
   Lecture SEULE du dernier `core.SlaSnapshot` (GET /core/sla/, NTOBS3) —
   aucun nouveau calcul ici. Dégrade EN SILENCE (la carte disparaît) tant
   qu'aucun snapshot n'existe encore pour la société (le job beat mensuel
   n'a pas encore tourné) — jamais un pourcentage inventé.
   ========================================================================== */

export default function SlaBadgeCard() {
  const navigate = useNavigate()
  const [dernier, setDernier] = useState(null) // null = en cours/indisponible

  useEffect(() => {
    let alive = true
    parametresApi.getSlaSnapshots()
      .then((res) => {
        if (!alive) return
        const snapshots = res.data ?? []
        setDernier(snapshots[0] ?? false)
      })
      .catch(() => { if (alive) setDernier(false) })
    return () => { alive = false }
  }, [])

  if (!dernier) return null

  const aller = () => navigate('/parametres/sla')
  const onKeyGo = (e) => { if (e.key === 'Enter') aller() }
  const pct = Number(dernier.uptime_pct)
  const pctAffiche = Number.isFinite(pct) ? pct.toFixed(2) : null
  if (pctAffiche === null) return null

  return (
    <div data-testid="sla-badge-card">
      <Card role="button" tabIndex={0} onClick={aller} onKeyDown={onKeyGo} className="cursor-pointer">
        <CardContent className="flex items-center gap-3 py-4">
          <ShieldCheck className="h-5 w-5 text-muted-foreground" aria-hidden="true" />
          <div className="flex-1">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">
              Disponibilité ce mois-ci
            </p>
            <p className="num mt-1 text-2xl font-semibold text-foreground">
              {pctAffiche}%
            </p>
            <p className="mt-1 text-xs text-muted-foreground underline">
              Voir le rapport SLA complet
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
