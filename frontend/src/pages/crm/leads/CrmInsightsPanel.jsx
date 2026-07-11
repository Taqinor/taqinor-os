import { useEffect, useState } from 'react'
import { Target, TrendingUp, AlarmClock } from 'lucide-react'
import crmApi from '../../../api/crmApi'
import {
  Card, CardHeader, CardTitle, CardDescription, CardContent, Badge, Spinner,
} from '../../../ui'
import { formatMAD, formatNumber } from '../../../lib/format'

// WR9 — surfaces consultatives du pipeline (lecture seule) :
//  - FG39 : atteinte des objectifs commerciaux (réalisé vs cible) ;
//  - FG34 : ROI par canal / campagne UTM ;
//  - FG28 : leads NEW non contactés au-delà du SLA société.
// Les règles vivent côté serveur ; ce panneau ne fait qu'afficher.

const fmtMAD = (v) => formatMAD(v)

const periodLabel = (o) => {
  if (o.period_type === 'month' && o.period_month) {
    return `${String(o.period_month).padStart(2, '0')}/${o.period_year}`
  }
  if (o.period_type === 'quarter' && o.period_quarter) {
    return `T${o.period_quarter} ${o.period_year}`
  }
  return String(o.period_year)
}

function SectionState({ loading, error, empty, emptyLabel, children }) {
  if (loading) {
    return (
      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        <Spinner className="size-4" /> Chargement…
      </p>
    )
  }
  if (error) {
    return (
      <p className="text-sm text-muted-foreground">
        Données indisponibles — réessayez.
      </p>
    )
  }
  if (empty) return <p className="text-sm text-muted-foreground">{emptyLabel}</p>
  return children
}

export default function CrmInsightsPanel() {
  const [attainment, setAttainment] = useState(null)
  const [roi, setRoi] = useState(null)
  const [sla, setSla] = useState(null)
  const [errors, setErrors] = useState({})

  useEffect(() => {
    let alive = true
    crmApi.getObjectifsAttainment()
      .then((r) => { if (alive) setAttainment(r.data ?? []) })
      .catch(() => { if (alive) { setAttainment([]); setErrors((e) => ({ ...e, attainment: true })) } })
    crmApi.getRoiSources()
      .then((r) => { if (alive) setRoi(r.data ?? []) })
      .catch(() => { if (alive) { setRoi([]); setErrors((e) => ({ ...e, roi: true })) } })
    crmApi.getSlaBreach()
      .then((r) => { if (alive) setSla(r.data ?? { count: 0, results: [] }) })
      .catch(() => { if (alive) { setSla({ count: 0, results: [] }); setErrors((e) => ({ ...e, sla: true })) } })
    return () => { alive = false }
  }, [])

  const slaResults = sla?.results ?? []

  return (
    <div className="mt-4 grid gap-4 lg:grid-cols-3" data-testid="crm-insights">
      {/* FG39 — objectifs commerciaux */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Target className="size-4 text-muted-foreground" aria-hidden="true" />
            Objectifs — atteinte
          </CardTitle>
          <CardDescription>Réalisé vs cible par vendeur / période</CardDescription>
        </CardHeader>
        <CardContent>
          <SectionState loading={attainment == null} error={errors.attainment}
                        empty={(attainment ?? []).length === 0}
                        emptyLabel="Aucun objectif défini.">
            <ul className="flex flex-col gap-2">
              {(attainment ?? []).map((o) => (
                <li key={o.id} className="rounded-lg border border-border p-2.5 text-sm">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="font-medium">
                      {o.metric_display} — {o.owner_nom ?? 'Équipe'}
                    </span>
                    <Badge tone={o.taux >= 100 ? 'success' : o.taux >= 60 ? 'warning' : 'neutral'}>
                      {Math.round(o.taux)} %
                    </Badge>
                  </div>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    {periodLabel(o)} · réalisé {formatNumber(o.realise)}
                    {' '}/ cible {formatNumber(o.cible)}
                  </p>
                </li>
              ))}
            </ul>
          </SectionState>
        </CardContent>
      </Card>

      {/* FG34 — ROI par source */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <TrendingUp className="size-4 text-muted-foreground" aria-hidden="true" />
            ROI par source
          </CardTitle>
          <CardDescription>Taux de signature et valeur signée par canal / campagne</CardDescription>
        </CardHeader>
        <CardContent>
          <SectionState loading={roi == null} error={errors.roi}
                        empty={(roi ?? []).length === 0}
                        emptyLabel="Aucune donnée de source.">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-muted-foreground">
                  <th className="py-1 pr-2 font-medium">Source</th>
                  <th className="py-1 pr-2 text-right font-medium">Leads</th>
                  <th className="py-1 pr-2 text-right font-medium">Signés</th>
                  <th className="py-1 text-right font-medium">Valeur TTC</th>
                </tr>
              </thead>
              <tbody>
                {(roi ?? []).map((r, i) => (
                  <tr key={`${r.canal}-${r.utm_campaign ?? i}`} className="border-t border-border">
                    <td className="py-1 pr-2">
                      {r.canal || '—'}
                      {r.utm_campaign ? (
                        <span className="text-xs text-muted-foreground"> · {r.utm_campaign}</span>
                      ) : null}
                    </td>
                    <td className="py-1 pr-2 text-right">{r.lead_count}</td>
                    <td className="py-1 pr-2 text-right">
                      {r.signed_count} ({r.win_rate} %)
                    </td>
                    <td className="py-1 text-right">{fmtMAD(r.signed_value_ttc)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </SectionState>
        </CardContent>
      </Card>

      {/* FG28 — retards SLA de premier contact */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <AlarmClock className="size-4 text-muted-foreground" aria-hidden="true" />
            SLA premier contact
            {sla != null && sla.count > 0 && (
              <Badge tone="danger">{sla.count}</Badge>
            )}
          </CardTitle>
          <CardDescription>
            {sla?.sla_hours
              ? `Leads NEW non contactés depuis plus de ${sla.sla_hours} h`
              : 'Leads NEW non contactés au-delà du délai société'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <SectionState loading={sla == null} error={errors.sla}
                        empty={slaResults.length === 0}
                        emptyLabel={sla?.sla_hours === 0
                          ? 'SLA désactivé (0 h) — configurable dans Paramètres → Leads.'
                          : 'Aucun lead en retard de premier contact.'}>
            <ul className="flex flex-col gap-1.5">
              {slaResults.slice(0, 10).map((l) => (
                <li key={l.id} className="flex items-center justify-between gap-2 rounded-lg border border-border p-2 text-sm">
                  <span className="font-medium">{l.nom}</span>
                  <span className="text-xs text-muted-foreground">
                    créé le {l.date_creation
                      ? new Date(l.date_creation).toLocaleDateString('fr-FR') : '—'}
                  </span>
                </li>
              ))}
              {slaResults.length > 10 && (
                <li className="text-xs text-muted-foreground">
                  … et {slaResults.length - 10} autre(s).
                </li>
              )}
            </ul>
          </SectionState>
        </CardContent>
      </Card>
    </div>
  )
}
