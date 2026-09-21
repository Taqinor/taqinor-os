import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle } from 'lucide-react'
import coreApi from '../../api/coreApi'
import {
  Card, CardContent, CardHeader, CardTitle, Badge, Spinner,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
  Input, Label, EmptyState,
} from '../../ui'
import { BarArrondie } from '../../ui/charts'
import PageHeader from '../../components/layout/PageHeader'

/* ============================================================================
   NTWFL24 — écran « Analyse de process » (`/workflow/analyse`).
   ----------------------------------------------------------------------------
   Sélectionner une définition affiche son entonnoir de durée (barres
   horizontales, `ui/charts/BarArrondie`, durée moyenne PAR étape dans l'ordre
   du processus) et surligne visuellement l'étape goulot — l'étape à la durée
   moyenne la plus élevée parmi celles réellement mesurées, calculée côté
   serveur (`core.selectors.analyse_goulots_workflow`), jamais recalculée ici.
   Un filtre période optionnel (`AAAA-MM`) restreint aux décisions de ce mois.
   ========================================================================== */

const AUCUNE_PERIODE = ''

function formatHeures(v) {
  if (v == null) return '—'
  return `${v.toFixed(1)} h`
}

function formatPct(v) {
  if (v == null) return '—'
  return `${Math.round(v * 100)} %`
}

export default function ProcessAnalytics() {
  const [definitions, setDefinitions] = useState([])
  const [definitionId, setDefinitionId] = useState('')
  const [periode, setPeriode] = useState(AUCUNE_PERIODE)
  const [analyse, setAnalyse] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    coreApi.workflowDefinitions.list()
      .then((r) => setDefinitions(Array.isArray(r.data) ? r.data : (r.data?.results ?? [])))
      .catch(() => setDefinitions([]))
  }, [])

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- reflète la sélection courante
    if (!definitionId) { setAnalyse(null); return }
    let vivant = true
    setLoading(true)
    setError(null)
    coreApi.workflowAnalyse.get(definitionId, periode || undefined)
      .then((r) => { if (vivant) setAnalyse(r.data) })
      .catch(() => { if (vivant) setError("Analyse indisponible pour cette définition.") })
      .finally(() => { if (vivant) setLoading(false) })
    return () => { vivant = false }
  }, [definitionId, periode])

  const donneesGraphique = useMemo(() => {
    const etapes = analyse?.etapes ?? []
    return etapes.map((e) => ({
      nom: e.nom,
      duree_moyenne_h: e.duree_moyenne_h ?? 0,
      color: e.goulot ? 'danger' : undefined,
    }))
  }, [analyse])

  return (
    <div className="mx-auto max-w-4xl space-y-4 p-4 sm:p-6">
      <PageHeader
        title="Analyse de process"
        subtitle="Durée observée par étape, taux de rejet/escalade et étape goulot."
      />

      <Card>
        <CardContent className="flex flex-wrap items-end gap-3 pt-4 sm:pt-5">
          <div className="flex flex-col gap-1">
            <Label htmlFor="analyse-definition">Définition</Label>
            <Select value={definitionId} onValueChange={setDefinitionId}>
              <SelectTrigger id="analyse-definition" className="w-64">
                <SelectValue placeholder="Choisir une définition…" />
              </SelectTrigger>
              <SelectContent>
                {definitions.map((d) => (
                  <SelectItem key={d.id} value={String(d.id)}>{d.nom}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="analyse-periode">Période (optionnelle)</Label>
            <Input
              id="analyse-periode"
              type="month"
              value={periode}
              onChange={(e) => setPeriode(e.target.value)}
              className="w-40"
            />
          </div>
        </CardContent>
      </Card>

      {!definitionId && (
        <EmptyState
          title="Aucune définition sélectionnée"
          description="Choisissez une définition de workflow pour afficher son analyse."
        />
      )}

      {definitionId && loading && (
        <div className="flex justify-center p-8"><Spinner /></div>
      )}

      {definitionId && !loading && error && (
        <p className="text-sm text-destructive">{error}</p>
      )}

      {definitionId && !loading && !error && analyse && (
        <>
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">
                Entonnoir de durée — {analyse.definition_nom}
                {analyse.nb_instances != null && (
                  <span className="ml-2 text-xs font-normal text-muted-foreground">
                    ({analyse.nb_instances} instance{analyse.nb_instances > 1 ? 's' : ''})
                  </span>
                )}
              </CardTitle>
            </CardHeader>
            <CardContent>
              {analyse.etapes.length === 0 ? (
                <p className="text-sm text-muted-foreground">Aucune étape.</p>
              ) : (
                <BarArrondie
                  data={donneesGraphique}
                  dataKey="duree_moyenne_h"
                  categoryKey="nom"
                  layout="vertical"
                  height={Math.max(160, analyse.etapes.length * 44)}
                  tooltipFormat={(v) => formatHeures(v)}
                  name="Durée moyenne"
                />
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Détail par étape</CardTitle>
            </CardHeader>
            <CardContent className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-xs text-muted-foreground">
                    <th className="py-1.5 pr-2">Étape</th>
                    <th className="py-1.5 pr-2 text-right">Décisions</th>
                    <th className="py-1.5 pr-2 text-right">Moyenne</th>
                    <th className="py-1.5 pr-2 text-right">Médiane</th>
                    <th className="py-1.5 pr-2 text-right">P90</th>
                    <th className="py-1.5 pr-2 text-right">Rejet</th>
                    <th className="py-1.5 pr-2 text-right">Escalade</th>
                  </tr>
                </thead>
                <tbody>
                  {analyse.etapes.map((e) => (
                    <tr
                      key={e.step_def_id}
                      className={e.goulot ? 'bg-destructive/10' : ''}
                    >
                      <td className="py-1.5 pr-2 font-medium">
                        {e.nom}
                        {e.goulot && (
                          <Badge tone="danger" className="ml-2">
                            <AlertTriangle size={12} aria-hidden="true" /> Goulot
                          </Badge>
                        )}
                      </td>
                      <td className="py-1.5 pr-2 text-right tabular-nums">{e.nb_decisions}</td>
                      <td className="py-1.5 pr-2 text-right tabular-nums">{formatHeures(e.duree_moyenne_h)}</td>
                      <td className="py-1.5 pr-2 text-right tabular-nums">{formatHeures(e.duree_mediane_h)}</td>
                      <td className="py-1.5 pr-2 text-right tabular-nums">{formatHeures(e.duree_p90_h)}</td>
                      <td className="py-1.5 pr-2 text-right tabular-nums">{formatPct(e.taux_rejet)}</td>
                      <td className="py-1.5 pr-2 text-right tabular-nums">{formatPct(e.taux_escalade)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  )
}
