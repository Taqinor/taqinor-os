import { useCallback, useEffect, useMemo, useState } from 'react'
import { Lock, Scale } from 'lucide-react'
import { ListShell } from '../../ui/module'
import {
  Button, Card, EmptyState, Label, Spinner, Stat, toast,
} from '../../ui'
import rhApi from '../../api/rhApi'

/* ============================================================================
   NTHCM6 — Calibration des révisions salariales (vue RH d'ensemble).
   ----------------------------------------------------------------------------
   Un manager ne voit que SON équipe (NTHCM5) : personne ne pouvait comparer
   les managers entre eux avant de figer. Cet écran est cette vue-là.

   DONNÉE DE PAIE — le serveur gate TOUT sur `salaires_voir` (gate de classe de
   `CycleRevisionSalarialeViewSet`) : cet écran n'élargit rien, il consomme.

   DEUX RÈGLES VISIBLES ICI :
   * les tranches de l'histogramme viennent du SERVEUR (`distribution`) — si
     l'écran les recalculait, deux écrans liraient deux distributions ;
   * valider la calibration FIGE le cycle une seule fois : quand `cycle.clos`
     est vrai, le bouton est désactivé et l'écran le dit, au lieu de laisser
     l'utilisateur découvrir le 400.
   ========================================================================== */

export default function CalibrationRevisions() {
  const [cycles, setCycles] = useState([])
  const [cycleId, setCycleId] = useState('')
  const [etat, setEtat] = useState({ data: null, loading: false, error: null })
  const [validation, setValidation] = useState(false)
  const { data, loading, error } = etat

  useEffect(() => {
    let vivant = true
    rhApi.getCyclesRevision()
      .then((res) => {
        if (!vivant) return
        const liste = Array.isArray(res.data)
          ? res.data
          : (res.data?.results ?? [])
        setCycles(liste)
      })
      .catch(() => {
        if (vivant) toast.error('Impossible de charger les cycles de révision.')
      })
    return () => { vivant = false }
  }, [])

  const charger = useCallback((id) => {
    if (!id) {
      setEtat({ data: null, loading: false, error: null })
      return Promise.resolve()
    }
    setEtat({ data: null, loading: true, error: null })
    return rhApi.getCalibrationCycle(id)
      .then((res) => setEtat({ data: res.data, loading: false, error: null }))
      .catch(() => {
        setEtat({
          data: null,
          loading: false,
          error: 'Impossible de charger la calibration de ce cycle.',
        })
        toast.error('Impossible de charger la calibration de ce cycle.')
      })
  }, [])

  const valider = useCallback(() => {
    if (!cycleId) return
    setValidation(true)
    rhApi.validerCalibrationCycle(cycleId)
      .then(() => {
        toast.success('Calibration validée : le cycle est figé.')
        return charger(cycleId)
      })
      .catch((err) => {
        const detail = err?.response?.data?.detail
        toast.error(detail || 'La validation de la calibration a échoué.')
      })
      .finally(() => setValidation(false))
  }, [cycleId, charger])

  const colonnes = useMemo(() => [
    {
      id: 'employe',
      header: 'Employé',
      width: 200,
      accessor: (p) => p.employe || '',
      cell: (v) => <span className="font-medium">{v || '—'}</span>,
    },
    {
      id: 'manager',
      header: 'Manager',
      width: 180,
      accessor: (p) => p.manager || '',
      cell: (v) => v || '—',
    },
    {
      id: 'augmentation',
      header: 'Augmentation proposée',
      width: 180,
      searchable: false,
      accessor: (p) => p.augmentation_pct_proposee ?? '',
      cell: (v) => (v === '' || v === null ? '—' : `${v} %`),
    },
    {
      id: 'tranche',
      header: 'Tranche',
      width: 110,
      searchable: false,
      accessor: (p) => p.tranche || '',
      cell: (v) => v || '—',
    },
    {
      id: 'statut',
      header: 'Statut',
      width: 120,
      accessor: (p) => p.statut || '',
      cell: (v) => v || '—',
    },
  ], [])

  const clos = Boolean(data?.cycle?.clos)
  const maxHistogramme = useMemo(() => Math.max(
    1,
    ...(data?.distribution ?? []).map((t) => t.nombre ?? 0),
  ), [data])

  return (
    <div className="page flex flex-col gap-4">
      <div className="page-header">
        <h2>Calibration des révisions</h2>
      </div>

      <Card className="flex flex-col gap-3 p-4 sm:flex-row sm:items-end">
        <div className="flex flex-col gap-1.5 sm:w-80">
          <Label htmlFor="cal-cycle">Cycle de révision</Label>
          <select
            id="cal-cycle"
            value={cycleId}
            onChange={(e) => {
              setCycleId(e.target.value)
              charger(e.target.value)
            }}
            className="h-9 rounded-md border border-border bg-card px-3 text-sm"
          >
            <option value="">Choisir un cycle…</option>
            {cycles.map((cycle) => (
              <option key={cycle.id} value={cycle.id}>
                {cycle.libelle}
              </option>
            ))}
          </select>
        </div>
        <div className="sm:ml-auto flex items-end gap-3">
          <Stat
            label="Propositions"
            value={data ? String(data.nb_propositions ?? 0) : '—'}
            hint={data ? `Cycle ${data.cycle?.statut ?? ''}` : 'Choisir un cycle'}
            icon={Scale}
          />
          <Button
            type="button"
            onClick={valider}
            disabled={!data || clos || validation}
          >
            <Lock className="size-4" aria-hidden="true" />
            {clos ? 'Cycle déjà figé' : 'Valider la calibration'}
          </Button>
        </div>
      </Card>

      {clos && (
        <p className="text-sm text-muted-foreground">
          Ce cycle est clos : les décisions sont figées et ne peuvent plus être
          modifiées.
        </p>
      )}

      {loading && (
        <Card className="flex items-center gap-2 p-4 text-sm text-muted-foreground">
          <Spinner className="size-4" /> Chargement de la calibration…
        </Card>
      )}
      {!loading && error && (
        <Card className="p-4 text-sm text-destructive">{error}</Card>
      )}
      {!loading && !error && !data && (
        <EmptyState
          icon={Scale}
          title="Aucun cycle sélectionné"
          description="Choisissez un cycle de révision pour comparer les managers."
        />
      )}

      {!loading && !error && data && (
        <>
          <Card className="flex flex-col gap-3 p-4">
            <h3 className="text-sm font-medium">
              Distribution des augmentations
            </h3>
            <ul className="flex flex-col gap-1.5">
              {data.distribution.map((tranche) => (
                <li key={tranche.tranche} className="flex items-center gap-2">
                  <span className="w-14 shrink-0 text-xs text-muted-foreground">
                    {tranche.tranche} %
                  </span>
                  <span className="h-3 flex-1 overflow-hidden rounded bg-muted">
                    <span
                      className="block h-full rounded bg-primary"
                      style={{
                        width: `${Math.round(
                          (100 * (tranche.nombre ?? 0)) / maxHistogramme)}%`,
                      }}
                    />
                  </span>
                  <span className="w-8 shrink-0 text-right text-xs tabular-nums">
                    {tranche.nombre}
                  </span>
                </li>
              ))}
            </ul>
          </Card>

          <Card className="flex flex-col gap-3 p-4">
            <h3 className="text-sm font-medium">
              Enveloppe consommée par manager
            </h3>
            {data.par_manager.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                Aucune enveloppe allouée sur ce cycle.
              </p>
            ) : (
              <ul className="flex flex-col gap-1.5">
                {data.par_manager.map((ligne) => (
                  <li
                    key={ligne.manager_id}
                    className="flex items-center justify-between gap-3 text-sm"
                  >
                    <span className="truncate">{ligne.manager}</span>
                    <span
                      className={ligne.depassement
                        ? 'shrink-0 tabular-nums text-destructive'
                        : 'shrink-0 tabular-nums text-muted-foreground'}
                    >
                      {ligne.enveloppe_consommee_pct} %
                      {' / '}
                      {ligne.enveloppe_allouee_pct} %
                      {ligne.depassement ? ' — dépassement' : ''}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <ListShell
            title="Propositions du cycle"
            subtitle="Tous managers confondus"
            columns={colonnes}
            rows={data.propositions}
            searchable
            exportName="calibration-revisions"
            emptyTitle="Aucune proposition"
            emptyDescription="Aucun manager n’a encore proposé de révision sur ce cycle."
          />
        </>
      )}
    </div>
  )
}
