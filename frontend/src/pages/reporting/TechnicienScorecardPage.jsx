import { useEffect, useMemo, useState } from 'react'
import { Award, UserCog } from 'lucide-react'
import api from '../../api/axios'
import reportingApi from '../../api/reportingApi'
import {
  Card, CardContent, EmptyState, Select, SelectTrigger, SelectValue,
  SelectContent, SelectItem, Spinner,
} from '../../ui'
import PageHeader from '../../components/layout/PageHeader'

/* ============================================================================
   XFSM17 — Scorecard technicien (coaching), `reporting/insights/
   technicien-scorecard/`. Combine interventions terminées, durée réelle vs
   estimée, récidive, ponctualité, NPS et utilisation — comparé à la MOYENNE
   ÉQUIPE. Réservé responsable/admin (jamais visible du technicien
   lui-même). `?technicien=<id>` est REQUIS côté backend.
   ========================================================================== */

const pct = (v) => (v == null ? '—' : `${v} %`)
const jours = (v) => (v == null ? '—' : `${v} j`)

function ScoreRow({ label, techValue, equipeValue, format = (v) => v }) {
  return (
    <tr className="border-b border-border/60 last:border-b-0">
      <td className="px-3 py-2 text-sm text-foreground">{label}</td>
      <td className="px-3 py-2 text-right text-sm font-medium tabular-nums">{format(techValue)}</td>
      <td className="px-3 py-2 text-right text-sm text-muted-foreground tabular-nums">{format(equipeValue)}</td>
    </tr>
  )
}

export default function TechnicienScorecardPage() {
  const [techniciens, setTechniciens] = useState([])
  const [technicienId, setTechnicienId] = useState('')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(false)

  useEffect(() => {
    let active = true
    api.get('/users/')
      .then((r) => { if (active) setTechniciens(r.data?.results ?? r.data ?? []) })
      .catch(() => { if (active) setTechniciens([]) })
    return () => { active = false }
  }, [])

  useEffect(() => {
    if (!technicienId) return undefined
    let active = true
    reportingApi.technicienScorecard({ technicien: technicienId })
      .then((r) => { if (active) { setData(r.data); setError(false) } })
      .catch(() => { if (active) { setData(null); setError(true) } })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [technicienId])

  const selectTechnicien = (id) => {
    setData(null)
    setLoading(true)
    setTechnicienId(id)
  }

  const technicienOptions = useMemo(
    () => techniciens.map((u) => ({ value: String(u.id), label: u.username })),
    [techniciens],
  )

  return (
    <div className="page">
      <PageHeader
        title="Scorecard technicien"
        subtitle="Coaching : interventions, durée réelle vs estimée, récidive, ponctualité, NPS, utilisation — vs moyenne équipe."
      />

      <div className="mb-4 flex flex-col gap-1">
        <span className="text-xs font-medium text-muted-foreground">Technicien</span>
        <Select value={technicienId} onValueChange={selectTechnicien}>
          <SelectTrigger className="w-64" aria-label="Choisir un technicien">
            <SelectValue placeholder="Choisir un technicien…" />
          </SelectTrigger>
          <SelectContent>
            {technicienOptions.map((o) => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>

      {!technicienId ? (
        <EmptyState
          icon={UserCog}
          title="Choisissez un technicien"
          description="Le scorecard s’affiche une fois un technicien sélectionné."
          className="my-6"
        />
      ) : loading ? (
        <p className="flex items-center gap-2 py-10 text-sm text-muted-foreground"><Spinner /> Chargement…</p>
      ) : error || !data ? (
        <EmptyState icon={Award} title="Erreur" description="Impossible de charger le scorecard." className="my-6" />
      ) : (
        <Card>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-sm" aria-label="Scorecard technicien vs moyenne équipe">
                <thead>
                  <tr className="border-b border-border">
                    <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground">Indicateur</th>
                    <th className="px-3 py-2 text-right text-xs font-semibold uppercase tracking-wide text-muted-foreground">Technicien</th>
                    <th className="px-3 py-2 text-right text-xs font-semibold uppercase tracking-wide text-muted-foreground">Moyenne équipe</th>
                  </tr>
                </thead>
                <tbody>
                  <ScoreRow
                    label="Interventions terminées"
                    techValue={data.scorecard?.interventions_terminees}
                    equipeValue={data.moyenne_equipe?.interventions_terminees}
                  />
                  <ScoreRow
                    label="Durée réelle moyenne"
                    techValue={data.scorecard?.duree_reelle_moyenne_jours}
                    equipeValue={data.moyenne_equipe?.duree_reelle_moyenne_jours}
                    format={jours}
                  />
                  <ScoreRow
                    label="% récidive"
                    techValue={data.scorecard?.taux_recidive_pct}
                    equipeValue={data.moyenne_equipe?.taux_recidive_pct}
                    format={pct}
                  />
                  <ScoreRow
                    label="% ponctualité"
                    techValue={data.scorecard?.ponctualite_pct}
                    equipeValue={data.moyenne_equipe?.ponctualite_pct}
                    format={pct}
                  />
                  <ScoreRow
                    label="NPS"
                    techValue={data.scorecard?.nps}
                    equipeValue={data.moyenne_equipe?.nps}
                  />
                  <ScoreRow
                    label="% utilisation"
                    techValue={data.scorecard?.utilisation_pct}
                    equipeValue={data.moyenne_equipe?.utilisation_pct}
                    format={pct}
                  />
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
