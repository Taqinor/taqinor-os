import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Lightbulb } from 'lucide-react'
import api from '../../api/axios'
import { Card, CardContent } from '../../ui'

/* ============================================================================
   NTIDE50 — Carte « Idées cette semaine » sur le cockpit direction, tuiles
   KPI innovation FÉDÉRÉES (``kpi_providers``, ARC40 — même mécanisme que
   ``CreditKpiCards``, WIR144) : compte de la semaine + top idée votée.
   Lecture seule, dégrade en silence si le flux est vide. Drill-down : clic
   → /innovation/idees.
   ========================================================================== */

const ENDPOINT = '/reporting/reports/kpi-federes/'

export default function InnovationKpiCard() {
  const navigate = useNavigate()
  const [tuiles, setTuiles] = useState(null) // null = en cours, [] = vide/erreur

  useEffect(() => {
    let alive = true
    api.get(ENDPOINT)
      .then((res) => {
        if (!alive) return
        const all = res.data?.tuiles ?? []
        setTuiles(all.filter((t) => String(t.id).startsWith('innovation_')))
      })
      .catch(() => { if (alive) setTuiles([]) })
    return () => { alive = false }
  }, [])

  // Rien à afficher tant que le flux n'a pas répondu ou s'il est vide.
  if (tuiles === null || tuiles.length === 0) return null

  const count = tuiles.find((t) => t.id === 'innovation_idees_semaine')
  const top = tuiles.find((t) => t.id === 'innovation_top_idee_semaine')
  const goToIdees = () => navigate('/innovation/idees')
  const onKeyGo = (e) => { if (e.key === 'Enter') goToIdees() }

  return (
    <div data-testid="innovation-kpi-federes">
      <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-foreground">
        <Lightbulb size={16} strokeWidth={1.75} aria-hidden="true" />
        Innovation
      </div>
      <div className="grid grid-cols-[repeat(auto-fit,minmax(170px,1fr))] gap-4">
        <Card role="button" tabIndex={0} onClick={goToIdees} onKeyDown={onKeyGo} className="cursor-pointer">
          <CardContent className="py-4">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">
              {count ? count.label : 'Idées cette semaine'}
            </p>
            <p className="num mt-1 text-2xl font-semibold text-foreground">
              {count ? count.valeur : 0}
            </p>
          </CardContent>
        </Card>
        {top && (
          <Card role="button" tabIndex={0} onClick={goToIdees} onKeyDown={onKeyGo} className="cursor-pointer">
            <CardContent className="py-4">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">
                {top.label}
              </p>
              <p className="num mt-1 text-2xl font-semibold text-foreground">
                {top.valeur} vote(s)
              </p>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  )
}
