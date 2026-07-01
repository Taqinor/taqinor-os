import { useCallback, useEffect, useState } from 'react'
import { CalendarRange, Flag, Camera } from 'lucide-react'
import { Card, Button, Spinner, EmptyState, Badge, toast } from '../../../ui'
import { formatDate } from '../../../lib/format'
import gestionProjetApi from '../../../api/gestionProjetApi'
import { errMessage, StatutJalon } from '../constants'
import GanttChart from '../GanttChart'
import ProjetPicker from '../components/ProjetPicker'

/* UX39 — Planning Gantt : phases / tâches / dépendances / jalons, baseline,
   calendriers & jours fériés. Gantt CSS/SVG léger (aucune lib Gantt). */

export default function PlanningPage() {
  const [projetId, setProjetId] = useState('')
  const [data, setData] = useState(null) // { taches, jalons, dependances, baseline, calendrier, feries }
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback(async (pid) => {
    if (!pid) { setData(null); return }
    setLoading(true)
    setError(null)
    try {
      const [taches, jalons, deps, bases, cals, feries] = await Promise.all([
        gestionProjetApi.getTaches({ projet: pid }),
        gestionProjetApi.getJalons({ projet: pid }),
        gestionProjetApi.getDependances({ projet: pid }),
        gestionProjetApi.getBaselines({ projet: pid }),
        gestionProjetApi.getCalendriers({ projet: pid }),
        gestionProjetApi.getJoursFeries({ projet: pid }),
      ])
      const asList = (r) => (Array.isArray(r.data) ? r.data : r.data?.results ?? [])
      setData({
        taches: asList(taches),
        jalons: asList(jalons),
        dependances: asList(deps),
        baselines: asList(bases),
        calendrier: asList(cals)[0] ?? null,
        feries: asList(feries),
      })
    } catch (err) {
      setError(errMessage(err, 'Chargement du planning impossible.'))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    let alive = true
    ;(async () => { if (alive) await load(projetId) })()
    return () => { alive = false }
  }, [projetId, load])

  const prendreBaseline = async () => {
    setBusy(true)
    try {
      await gestionProjetApi.prendreBaseline(projetId, { libelle: `Baseline ${formatDate(new Date())}` })
      toast.success('Baseline figée.')
      load(projetId)
    } catch (err) {
      toast.error(errMessage(err, 'Baseline impossible.'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-display text-xl font-semibold tracking-tight">Planning Gantt</h1>
          <p className="text-sm text-muted-foreground">Sélectionnez un projet pour visualiser son planning.</p>
        </div>
        <div className="flex items-end gap-2">
          <ProjetPicker value={projetId} onChange={setProjetId} />
          {projetId && (
            <Button variant="outline" size="sm" disabled={busy} onClick={prendreBaseline}>
              <Camera /> Figer une baseline
            </Button>
          )}
        </div>
      </div>

      {!projetId ? (
        <EmptyState icon={CalendarRange} title="Aucun projet sélectionné" description="Choisissez un projet pour afficher son diagramme de Gantt." />
      ) : loading ? (
        <div className="flex justify-center p-10"><Spinner /></div>
      ) : error ? (
        <EmptyState title="Erreur" description={error} action={<Button variant="outline" onClick={() => load(projetId)}>Réessayer</Button>} />
      ) : (
        <>
          <Card className="p-4 sm:p-5">
            <GanttChart
              taches={data?.taches ?? []}
              jalons={data?.jalons ?? []}
              dependances={data?.dependances ?? []}
              baseline={[]}
            />
          </Card>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card className="p-4 sm:p-5">
              <h3 className="mb-3 font-display text-base font-semibold">Jalons</h3>
              {(data?.jalons ?? []).length ? (
                <ul className="flex flex-col gap-2">
                  {data.jalons.map((j) => (
                    <li key={j.id} className="flex items-center gap-2 text-sm">
                      <Flag className="size-4 text-amber-600" aria-hidden="true" />
                      <span className="font-medium">{j.libelle}</span>
                      <StatutJalon status={j.statut} />
                      <span className="ml-auto text-xs text-muted-foreground">{j.date_prevue ? formatDate(j.date_prevue) : '—'}</span>
                    </li>
                  ))}
                </ul>
              ) : <p className="text-sm text-muted-foreground">Aucun jalon.</p>}
            </Card>

            <Card className="p-4 sm:p-5">
              <h3 className="mb-3 font-display text-base font-semibold">Calendrier & jours fériés</h3>
              {data?.calendrier ? (
                <div className="flex flex-col gap-2 text-sm">
                  <div className="flex flex-wrap gap-1.5">
                    {[['Lun', data.calendrier.lundi], ['Mar', data.calendrier.mardi], ['Mer', data.calendrier.mercredi], ['Jeu', data.calendrier.jeudi], ['Ven', data.calendrier.vendredi], ['Sam', data.calendrier.samedi], ['Dim', data.calendrier.dimanche]].map(([lbl, on]) => (
                      <Badge key={lbl} tone={on ? 'success' : 'neutral'}>{lbl}</Badge>
                    ))}
                  </div>
                  {(data.feries ?? []).length ? (
                    <ul className="mt-2 flex flex-col gap-1 text-xs text-muted-foreground">
                      {data.feries.map((f) => (
                        <li key={f.id}>{formatDate(f.date)} — {f.libelle}</li>
                      ))}
                    </ul>
                  ) : <span className="text-xs text-muted-foreground">Aucun jour férié déclaré.</span>}
                </div>
              ) : <p className="text-sm text-muted-foreground">Aucun calendrier défini pour ce projet.</p>}
            </Card>
          </div>

          {(data?.baselines ?? []).length > 0 && (
            <Card className="p-4 sm:p-5">
              <h3 className="mb-3 font-display text-base font-semibold">Baselines</h3>
              <ul className="flex flex-col gap-1 text-sm">
                {data.baselines.map((b) => (
                  <li key={b.id} className="flex items-center gap-2">
                    <span className="font-medium">{b.libelle || `Baseline #${b.id}`}</span>
                    <Badge tone="info">{b.nb_lignes} tâches</Badge>
                    <span className="ml-auto text-xs text-muted-foreground">{b.date_creation ? formatDate(b.date_creation) : ''}</span>
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </>
      )}
    </div>
  )
}
