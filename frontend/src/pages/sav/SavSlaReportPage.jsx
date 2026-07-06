// XSAV8 — Rapport de conformité SLA + KPI avancés SAV. Réservé
// responsable/admin. % première réponse / résolution dans les délais (par
// priorité et technicien), délais moyens, backlog vieilli, préventif vs
// correctif, ponctualité des visites préventives, taux de réouverture.
import { useEffect, useState } from 'react'
import { Download, Gauge } from 'lucide-react'
import savApi from '../../api/savApi'
import {
  TooltipProvider, Card, Stat, Button, EmptyState, Skeleton,
} from '../../ui'

const pct = (v) => (v == null ? '—' : `${v} %`)
const jours = (v) => (v == null ? '—' : `${v} j`)

export default function SavSlaReportPage() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)

  const load = () => {
    setLoading(true)
    setLoadError(false)
    savApi.getSavSlaReport()
      .then((r) => setData(r.data))
      .catch(() => setLoadError(true))
      .finally(() => setLoading(false))
  }
  useEffect(() => { load() }, [])

  const exportXlsx = () => {
    // Ouvre l'export xlsx généré côté serveur (même patron que les autres
    // rapports reporting : lien direct, le navigateur gère le téléchargement).
    window.open('/api/django/reporting/insights/sav-sla/?export=xlsx', '_blank')
  }

  if (loading) {
    return (
      <div className="ui-root mx-auto flex max-w-5xl flex-col gap-4 p-1">
        {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-24 w-full" />)}
      </div>
    )
  }
  if (loadError || !data) {
    return (
      <div className="ui-root mx-auto max-w-5xl p-1">
        <EmptyState title="Chargement impossible"
                    description="Le rapport SLA n'a pas pu être chargé. Réessayez."
                    action={<Button size="sm" variant="outline" onClick={load}>Réessayer</Button>} />
      </div>
    )
  }

  return (
    <TooltipProvider delayDuration={200}>
      <div className="ui-root mx-auto flex max-w-5xl flex-col gap-5 p-1">
        <header className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="font-display text-2xl font-bold tracking-tight">Rapport SLA SAV</h1>
            <p className="text-sm text-muted-foreground">
              {data.total_tickets} ticket{data.total_tickets > 1 ? 's' : ''} évalué{data.total_tickets > 1 ? 's' : ''}
            </p>
          </div>
          <Button variant="outline" size="sm" onClick={exportXlsx}>
            <Download /> Export xlsx
          </Button>
        </header>

        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Card className="p-4"><Stat label="Délai moyen 1ère réponse" value={jours(data.delai_moyen_premiere_reponse_jours)} /></Card>
          <Card className="p-4"><Stat label="Délai moyen résolution" value={jours(data.delai_moyen_resolution_jours)} /></Card>
          <Card className="p-4"><Stat label="% préventif" value={pct(data.preventif_vs_correctif?.pct_preventif)} /></Card>
          <Card className="p-4"><Stat label="Visites préventives à l'heure" value={pct(data.visites_preventives?.pct_a_heure)} /></Card>
        </div>

        {/* Backlog vieilli */}
        <Card className="p-4">
          <h3 className="mb-3 font-display text-base font-semibold">Backlog vieilli (tickets ouverts)</h3>
          <div className="grid gap-3 sm:grid-cols-3">
            <Stat label="0-2 j" value={data.backlog_vieilli?.buckets?.['0_2j'] ?? 0} />
            <Stat label="3-7 j" value={data.backlog_vieilli?.buckets?.['3_7j'] ?? 0} />
            <Stat label="Plus de 7 j" value={data.backlog_vieilli?.buckets?.plus_7j ?? 0} />
          </div>
        </Card>

        {/* Par priorité */}
        <Card className="overflow-x-auto p-4">
          <h3 className="mb-3 font-display text-base font-semibold">Par priorité</h3>
          {(data.par_priorite ?? []).length === 0 ? (
            <p className="text-sm text-muted-foreground">Aucune donnée.</p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-muted-foreground">
                  <th className="pb-2">Priorité</th>
                  <th className="pb-2">Total</th>
                  <th className="pb-2">% 1ère réponse OK</th>
                  <th className="pb-2">% résolution OK</th>
                </tr>
              </thead>
              <tbody>
                {data.par_priorite.map((p) => (
                  <tr key={p.priorite} className="border-t border-border">
                    <td className="py-1.5">{p.label}</td>
                    <td className="py-1.5">{p.total}</td>
                    <td className="py-1.5">{pct(p.pct_premiere_reponse_ok)}</td>
                    <td className="py-1.5">{pct(p.pct_resolution_ok)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>

        {/* Par technicien */}
        <Card className="overflow-x-auto p-4">
          <h3 className="mb-3 flex items-center gap-2 font-display text-base font-semibold">
            <Gauge className="size-4 text-muted-foreground" aria-hidden="true" />
            Par technicien
          </h3>
          {(data.par_technicien ?? []).length === 0 ? (
            <p className="text-sm text-muted-foreground">Aucune donnée.</p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-muted-foreground">
                  <th className="pb-2">Technicien</th>
                  <th className="pb-2">Total</th>
                  <th className="pb-2">% 1ère réponse OK</th>
                  <th className="pb-2">% résolution OK</th>
                  <th className="pb-2">Réouvertures</th>
                </tr>
              </thead>
              <tbody>
                {data.par_technicien.map((t) => (
                  <tr key={t.technicien_id ?? 'none'} className="border-t border-border">
                    <td className="py-1.5">{t.technicien}</td>
                    <td className="py-1.5">{t.total}</td>
                    <td className="py-1.5">{pct(t.pct_premiere_reponse_ok)}</td>
                    <td className="py-1.5">{pct(t.pct_resolution_ok)}</td>
                    <td className="py-1.5">{t.reouvertures}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
      </div>
    </TooltipProvider>
  )
}
