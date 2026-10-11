// ASAV103 (D-ASAV-4 option (b), ASAV93) — pertes de production PAR CATÉGORIE
// d'un système supervisé (salissure, ombrage, panne, écrêtement — NTNRG32).
// Une catégorie sans donnée exploitable est servie `null` et affichée « non
// mesurable » — jamais un 0 % trompeur. Contrat :
// `apps/monitoring/contract_samples/pertes_categorisees.json`.
import { useEffect, useState } from 'react'
import monitoringApi from '../../../api/monitoringApi'
import { getApiError } from '../../../lib/apiError'
import { formatNumber } from '../../../lib/format'
import {
  Card, Select, SelectTrigger, SelectValue, SelectContent, SelectItem, Skeleton,
} from '../../../ui'
import SystemPicker from '../../../pages/monitoring/SystemPicker'

const CATEGORIES = [
  { cle: 'soiling_pct', label: 'Salissure' },
  { cle: 'ombrage_pct', label: 'Ombrage' },
  { cle: 'panne_pct', label: 'Panne (jours en sous-performance)' },
  { cle: 'curtailment_pct', label: 'Écrêtement / limitation' },
]
const FENETRES = ['30', '90', '365']

export default function PertesCategoriseesSection({ systems, loadingSystems }) {
  const [systeme, setSysteme] = useState('')
  const [fenetre, setFenetre] = useState('365')
  const [pertes, setPertes] = useState(null)
  const [loading, setLoading] = useState(false)
  const [erreur, setErreur] = useState(null)

  useEffect(() => {
    if (!systeme) return undefined
    let actif = true
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true)
    setErreur(null)
    monitoringApi.getPertesCategorisees(systeme, { window_days: fenetre })
      .then((r) => { if (actif) setPertes(r.data) })
      .catch((e) => {
        if (!actif) return
        setPertes(null)
        setErreur(getApiError(e, 'Pertes indisponibles.').message)
      })
      .finally(() => { if (actif) setLoading(false) })
    return () => { actif = false }
  }, [systeme, fenetre])

  return (
    <Card role="region" className="flex flex-col gap-3 p-4" aria-label="Pertes catégorisées">
      <h2 className="text-lg font-semibold">Pertes catégorisées</h2>
      <div className="flex flex-wrap items-center gap-3">
        <SystemPicker systems={systems} loading={loadingSystems} value={systeme} onChange={setSysteme} />
        <Select value={fenetre} onValueChange={setFenetre}>
          <SelectTrigger className="w-40" aria-label="Fenêtre d'analyse"><SelectValue /></SelectTrigger>
          <SelectContent>
            {FENETRES.map((f) => <SelectItem key={f} value={f}>{f} jours</SelectItem>)}
          </SelectContent>
        </Select>
      </div>
      {erreur && <p role="alert" className="text-sm text-destructive">{erreur}</p>}
      {loading ? (
        <Skeleton className="h-9 w-full" />
      ) : pertes && (
        <dl className="grid gap-2 sm:grid-cols-4">
          {CATEGORIES.map(({ cle, label }) => (
            <div key={cle} className="rounded-lg border border-border bg-card p-3">
              <dt className="text-xs text-muted-foreground">{label}</dt>
              <dd className="text-lg font-semibold">
                {pertes[cle] === null || pertes[cle] === undefined
                  ? 'non mesurable'
                  : `${formatNumber(pertes[cle], { decimals: 2 })} %`}
              </dd>
            </div>
          ))}
        </dl>
      )}
    </Card>
  )
}
