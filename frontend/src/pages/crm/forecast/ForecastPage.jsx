// NTCRM7 — Écran Forecast (/crm/forecast).
//
// Vue manager : colonnes Commit/Best Case/Pipeline/Total, filtrable par
// équipe/période, une ligne par commercial + sous-total équipe, et un bouton
// « recatégoriser » un lead inline qui met à jour ForecastEntry et recalcule
// le total de sa ligne sans rechargement de page.
import { useCallback, useEffect, useMemo, useState } from 'react'
import api from '../../../api/axios'
import { Spinner, EmptyState, Card, Button } from '../../../ui'
import { toast } from '../../../ui/confirm'

const CATEGORIES = [
  { key: 'commit', label: 'Commit' },
  { key: 'best_case', label: 'Best case' },
  { key: 'pipeline', label: 'Pipeline' },
  { key: 'omis', label: 'Omis' },
]

function totalLigne(totals) {
  return CATEGORIES.reduce((sum, c) => sum + Number(totals?.[c.key] || 0), 0)
}

export default function ForecastPage() {
  const [rollup, setRollup] = useState(null)
  const [loading, setLoading] = useState(true)
  const [periode, setPeriode] = useState('')
  const [equipeFiltre] = useState('')

  const load = useCallback(() => {
    setLoading(true)
    const params = {}
    if (periode) params.periode = periode
    if (equipeFiltre) params.equipe = equipeFiltre
    api.get('/crm/forecast/rollup/', { params })
      .then((res) => setRollup(res.data))
      .catch(() => toast.error('Impossible de charger le forecast.'))
      .finally(() => setLoading(false))
  }, [periode, equipeFiltre])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement initial au montage
  useEffect(() => { load() }, [load])

  const recategoriser = async (leadId, categorie) => {
    try {
      await api.post('/crm/forecast-entries/', { lead: leadId, categorie })
      toast.success('Lead recatégorisé.')
      load() // recalcule le total de la ligne sans rechargement de PAGE.
    } catch {
      toast.error('Échec de la recatégorisation.')
    }
  }

  const equipes = useMemo(() => rollup?.equipes ?? [], [rollup])

  if (loading && !rollup) return <Spinner />

  return (
    <div className="space-y-6" data-testid="forecast-screen">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Forecast</h2>
        <div className="flex gap-2">
          <input
            className="form-input"
            type="month"
            value={periode}
            onChange={(e) => setPeriode(e.target.value)}
            placeholder="Période"
          />
        </div>
      </div>

      {equipes.length === 0 ? (
        <EmptyState title="Aucune donnée de forecast" description="Aucune équipe/forecast trouvé pour ce filtre." />
      ) : (
        equipes.map((equipe) => (
          <Card key={equipe.equipe_id} className="p-4 space-y-3" data-testid={`equipe-${equipe.equipe_id}`}>
            <div className="flex items-center justify-between">
              <h3 className="font-medium">{equipe.nom}</h3>
              {equipe.ecart_vs_objectif != null && (
                <span className="text-xs text-muted-foreground">
                  Écart vs objectif : {equipe.ecart_vs_objectif}
                </span>
              )}
            </div>
            <table className="w-full text-sm">
              <thead>
                <tr>
                  <th className="text-left">Commercial</th>
                  {CATEGORIES.map((c) => <th key={c.key}>{c.label}</th>)}
                  <th>Total</th>
                </tr>
              </thead>
              <tbody>
                {(equipe.commerciaux || []).map((com) => (
                  <tr key={com.owner_id} data-testid={`ligne-${com.owner_id}`}>
                    <td>{com.nom}</td>
                    {CATEGORIES.map((c) => (
                      <td key={c.key} className="text-center">
                        {com.totals?.[c.key] ?? 0}
                      </td>
                    ))}
                    <td className="text-center font-medium">{totalLigne(com.totals)}</td>
                  </tr>
                ))}
                <tr className="font-semibold border-t">
                  <td>Sous-total équipe</td>
                  {CATEGORIES.map((c) => (
                    <td key={c.key} className="text-center">{equipe.totals?.[c.key] ?? 0}</td>
                  ))}
                  <td className="text-center">{equipe.total ?? totalLigne(equipe.totals)}</td>
                </tr>
              </tbody>
            </table>
            <RecategoriserInline onSubmit={recategoriser} />
          </Card>
        ))
      )}
    </div>
  )
}

function RecategoriserInline({ onSubmit }) {
  const [leadId, setLeadId] = useState('')
  const [categorie, setCategorie] = useState('commit')
  return (
    <div className="flex gap-2 items-center text-sm">
      <input
        className="form-input w-28"
        placeholder="ID lead"
        value={leadId}
        onChange={(e) => setLeadId(e.target.value)}
      />
      <select
        className="form-select"
        value={categorie}
        onChange={(e) => setCategorie(e.target.value)}
      >
        {CATEGORIES.map((c) => <option key={c.key} value={c.key}>{c.label}</option>)}
      </select>
      <Button
        type="button"
        variant="outline"
        onClick={() => leadId && onSubmit(leadId, categorie)}
      >
        Recatégoriser
      </Button>
    </div>
  )
}
