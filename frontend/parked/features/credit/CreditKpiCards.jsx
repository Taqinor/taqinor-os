import { useEffect, useState } from 'react'
import { Landmark } from 'lucide-react'
import api from '../../api/axios'
import { Card, CardContent } from '../../ui'

/* ============================================================================
   WIR144 — Tuiles KPI crédit FÉDÉRÉES sur un tableau de bord réel.
   ----------------------------------------------------------------------------
   20 apps déclarent des `kpi_providers` (core.platform) mais aucun écran ne
   consommait ce flux. Ici on affiche les 3 KPI crédit
   (`credit.selectors.kpi_credit` : DSO pondéré, taux de dérogations,
   répartition par score) en filtrant les tuiles fédérées `credit_*` de
   l'endpoint reporting `kpi-federes` (ARC40, mécanisme distinct de WIR100 mais
   qui s'y réfère). Lecture seule, dégrade en silence si le flux est vide.
   ========================================================================== */

const ENDPOINT = '/reporting/reports/kpi-federes/'

function formatValeur(tuile) {
  if (tuile.id === 'credit_taux_derogations') {
    return `${Math.round((tuile.valeur ?? 0) * 100)} %`
  }
  const unite = tuile.unite ? ` ${tuile.unite}` : ''
  return `${tuile.valeur}${unite}`
}

export default function CreditKpiCards() {
  const [tuiles, setTuiles] = useState(null) // null = en cours, [] = vide/erreur

  useEffect(() => {
    let alive = true
    api.get(ENDPOINT)
      .then((res) => {
        if (!alive) return
        const all = res.data?.tuiles ?? []
        setTuiles(all.filter((t) => String(t.id).startsWith('credit_')))
      })
      .catch(() => { if (alive) setTuiles([]) })
    return () => { alive = false }
  }, [])

  // Rien à afficher tant que le flux n'a pas répondu ou s'il est vide (aucune
  // donnée crédit) — on n'invente jamais une carte à zéro.
  if (tuiles === null || tuiles.length === 0) return null

  const dso = tuiles.find((t) => t.id === 'credit_dso_pondere')
  const taux = tuiles.find((t) => t.id === 'credit_taux_derogations')
  const scores = tuiles
    .filter((t) => t.id.startsWith('credit_score_'))
    .sort((a, b) => a.id.localeCompare(b.id))
  const headline = [dso, taux].filter(Boolean)

  return (
    <div data-testid="credit-kpi-federes">
      <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-foreground">
        <Landmark size={16} strokeWidth={1.75} aria-hidden="true" />
        Risque crédit
      </div>
      <div className="grid grid-cols-[repeat(auto-fit,minmax(170px,1fr))] gap-4">
        {headline.map((t) => (
          <Card key={t.id}>
            <CardContent className="py-4">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">
                {t.label}
              </p>
              <p className="num mt-1 text-2xl font-semibold text-foreground">
                {formatValeur(t)}
              </p>
            </CardContent>
          </Card>
        ))}
        {scores.length > 0 && (
          <Card>
            <CardContent className="py-4">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">
                Répartition par score
              </p>
              <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-sm">
                {scores.map((s) => (
                  <span key={s.id} className="text-foreground">
                    <span className="font-semibold">{s.id.slice(-1).toUpperCase()}</span>
                    {' '}{s.valeur}
                  </span>
                ))}
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  )
}
