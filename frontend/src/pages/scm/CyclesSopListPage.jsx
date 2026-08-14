import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus, CalendarClock } from 'lucide-react'
import scmApi from '../../api/scmApi'
import { Button, Badge, EmptyState, Skeleton } from '../../ui'
import { StateBlock } from '../../components/StateBlock'

/* ============================================================================
   NTSCM12 — Liste des cycles de planification S&OP, point d'entrée vers
   l'écran détaillé `/scm/sop/:id` (Demande/Offre/Finance).
   ========================================================================== */

const STATUT_META = {
  brouillon: { label: 'Brouillon', tone: 'neutral' },
  revue_demande: { label: 'Revue de la demande', tone: 'info' },
  revue_offre: { label: "Revue de l'offre", tone: 'info' },
  revue_finance: { label: 'Revue financière', tone: 'info' },
  reunion_reconciliation: { label: 'Réunion de réconciliation', tone: 'warning' },
  approuve: { label: 'Approuvé', tone: 'success' },
  clos: { label: 'Clos', tone: 'success' },
}

const moisEnCours = () => new Date().toISOString().slice(0, 7)

export default function CyclesSopListPage() {
  const navigate = useNavigate()
  const [cycles, setCycles] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(null)
  const [creerBusy, setCreerBusy] = useState(false)
  const [creerErr, setCreerErr] = useState(null)

  const charger = useCallback(() => {
    setLoading(true)
    setLoadError(null)
    return scmApi.cyclesSop()
      .then((r) => setCycles(r.data?.results ?? r.data ?? []))
      .catch((e) => setLoadError(
        e?.response?.data?.detail ?? 'Les cycles S&OP n\'ont pas pu être chargés.'))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { charger() }, [charger])

  const creerCycle = async () => {
    setCreerBusy(true); setCreerErr(null)
    try {
      const r = await scmApi.creerCycleSop({ periode: moisEnCours() })
      navigate(`/scm/sop/${r.data.id}`)
    } catch (e) {
      setCreerErr(e?.response?.data?.periode?.[0]
        ?? e?.response?.data?.detail
        ?? 'La création du cycle a échoué.')
    } finally {
      setCreerBusy(false)
    }
  }

  return (
    <div className="ui-root page">
      <div className="page-header" style={{ marginBottom: '1.25rem' }}>
        <h2>Cycles S&amp;OP</h2>
        <p className="text-sm text-muted-foreground">
          Cycle de planification mensuel demande/offre/finance (S&amp;OP).
        </p>
      </div>

      <div className="mb-4 flex items-center gap-2">
        <Button type="button" size="sm" loading={creerBusy} onClick={creerCycle}>
          <Plus /> Nouveau cycle ({moisEnCours()})
        </Button>
        {creerErr && <span className="text-sm text-destructive" role="alert">{creerErr}</span>}
      </div>

      {loading ? (
        <Skeleton className="h-48 w-full" />
      ) : loadError ? (
        <StateBlock error={loadError} onRetry={charger} />
      ) : cycles.length === 0 ? (
        <EmptyState
          icon={CalendarClock}
          title="Aucun cycle S&OP"
          description="Créez le premier cycle du mois en cours pour démarrer la planification."
        />
      ) : (
        <div className="flex flex-col gap-2">
          {cycles.map((cycle) => {
            const meta = STATUT_META[cycle.statut] ?? { label: cycle.statut, tone: 'neutral' }
            return (
              <button
                key={cycle.id}
                type="button"
                onClick={() => navigate(`/scm/sop/${cycle.id}`)}
                className="flex items-center justify-between rounded-lg border border-border bg-card p-3 text-left text-sm hover:bg-muted/40"
              >
                <span className="font-medium">{cycle.periode}</span>
                <Badge tone={meta.tone}>{meta.label}</Badge>
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
