import { useEffect, useRef, useState } from 'react'
import { RefreshCw } from 'lucide-react'
import ventesApi from '../../api/ventesApi'
import { Button, Card, Spinner, Stat, toast } from '../../ui'
import { frenchError } from '../../lib/frenchError'
import { formatMAD, formatNumber, formatPercent } from '../../lib/format'

/* ============================================================================
   PV76 — Carte « Étude bancable » de la fiche devis.
   ----------------------------------------------------------------------------
   LECTURE SEULE de `Devis.etude_params.simulation` (PV69/PV74 —
   `apps.ventes.etude` + le contrat partagé
   `apps/ventes/contract_samples/simulation.json`) : P50/P90, ratio de
   performance, mini-cascade des pertes, payback rigoureux (année), VAN/TRI sur
   25 ans. « Recalculer l'étude » relance le MÊME calcul asynchrone que PV74
   (`POST .../simuler/` → 202 + jeton, sondé jusqu'à `{status:'ready'}`) puis
   demande au parent de rafraîchir la liste (`onRefresh`) — la charge affichée
   vient TOUJOURS du devis relu, jamais recopiée depuis le cache du job.
   ========================================================================== */

const PERTES_LABELS = {
  temperature: 'Température',
  soiling: 'Salissure',
  shading: 'Ombrage',
  wiring: 'Câblage',
  inverter: 'Onduleur',
  mismatch: 'Mismatch',
  availability: 'Disponibilité',
}

const POLL_INTERVAL_MS = 3000

export default function EtudeBancable({ devis, onRefresh }) {
  const simulation = devis?.etude_params?.simulation || null
  const [busy, setBusy] = useState(false)
  const timerRef = useRef(null)
  const mountedRef = useRef(true)

  useEffect(() => () => {
    mountedRef.current = false
    if (timerRef.current) clearTimeout(timerRef.current)
  }, [])

  const lancerSimulation = async () => {
    setBusy(true)
    try {
      const res = await ventesApi.simulerEtudeDevis(devis.id)
      const jobId = res.data?.job_id
      const poll = async () => {
        try {
          const statusRes = await ventesApi.getSimulationStatus(devis.id, jobId)
          const etat = statusRes.data?.status
          if (etat === 'ready') {
            if (mountedRef.current) setBusy(false)
            onRefresh?.()
            toast.success('Étude bancable recalculée.')
            return
          }
          if (etat === 'error') {
            if (mountedRef.current) setBusy(false)
            toast.error("L'étude bancable a échoué.")
            return
          }
        } catch {
          // Sondage manqué — on continue, comme le polling PDF existant (QG1).
        }
        if (mountedRef.current) {
          timerRef.current = setTimeout(poll, POLL_INTERVAL_MS)
        }
      }
      timerRef.current = setTimeout(poll, POLL_INTERVAL_MS)
    } catch (err) {
      if (mountedRef.current) setBusy(false)
      toast.error(frenchError(err, 'Lancement de la simulation impossible.'))
    }
  }

  if (!simulation) {
    return (
      <div className="space-y-2">
        <p className="text-sm text-muted-foreground">
          Aucune étude bancable pour ce devis.
        </p>
        <Button size="sm" onClick={lancerSimulation} disabled={busy}>
          {busy ? <Spinner className="size-3.5" /> : <RefreshCw className="size-3.5" aria-hidden="true" />}
          Lancer la simulation
        </Button>
      </div>
    )
  }

  const pr = simulation.pr || {}
  const projection = simulation.projection_25y || {}
  const warnings = simulation.warnings || []
  const pertes = pr.loss_breakdown || {}

  return (
    <Card className="max-w-3xl space-y-4 p-4">
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm font-medium">Étude bancable</p>
        <Button size="sm" variant="outline" onClick={lancerSimulation} disabled={busy}>
          {busy ? <Spinner className="size-3.5" /> : <RefreshCw className="size-3.5" aria-hidden="true" />}
          Recalculer l'étude
        </Button>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <Stat label="P50" value={`${formatNumber(pr.p50_kwh, { decimals: 0 })} kWh`} />
        <Stat label="P90" value={`${formatNumber(pr.p90_kwh, { decimals: 0 })} kWh`} />
        <Stat
          label="Ratio de performance"
          value={pr.performance_ratio != null
            ? formatPercent(pr.performance_ratio * 100, { decimals: 1 })
            : '—'}
        />
        <Stat
          label="Retour sur investissement"
          value={projection.payback_year != null ? `${projection.payback_year} ans` : '—'}
        />
        <Stat
          label="VAN (25 ans)"
          value={projection.npv != null ? formatMAD(projection.npv, { decimals: 0 }) : '—'}
        />
        <Stat
          label="TRI"
          value={projection.irr != null ? formatPercent(projection.irr * 100, { decimals: 1 }) : '—'}
        />
      </div>

      {Object.keys(pertes).length > 0 && (
        <div>
          <p className="mb-1 text-xs font-medium text-muted-foreground">
            Cascade des pertes
          </p>
          <ul className="space-y-0.5 text-sm">
            {Object.entries(pertes).map(([cle, valeur]) => (
              <li key={cle} className="flex items-baseline justify-between gap-2">
                <span>{PERTES_LABELS[cle] || cle}</span>
                <span className="tabular-nums text-muted-foreground">
                  {formatPercent(valeur, { decimals: 1 })}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {warnings.length > 0 && (
        <ul className="space-y-0.5 text-xs text-warning">
          {warnings.map((w, i) => <li key={i}>{w}</li>)}
        </ul>
      )}
    </Card>
  )
}
