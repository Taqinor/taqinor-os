import { useEffect, useMemo, useState } from 'react'
import fpaApi from '../../api/fpaApi'
import { Button, Card } from '../../ui'
import PageHeader from '../../components/layout/PageHeader'
import { formatMAD } from '../../lib/format'

/* ============================================================================
   NTFPA17 — Écran Scénarios côte-à-côte.
   ----------------------------------------------------------------------------
   Sélection multi-scénario, tableau comparatif (base + une colonne par
   scénario, écart total annuel), bouton "Promouvoir en budget de base" (copie
   les deltas dans les lignes réelles du cycle, réservé FP&A/Directeur). La
   promotion crée un audit-log et fige l'ancien budget de base en archivé.
   ========================================================================== */

export default function ScenariosPage() {
  const [cycles, setCycles] = useState([])
  const [cycleId, setCycleId] = useState('')
  const [scenarios, setScenarios] = useState([])
  const [selection, setSelection] = useState([])
  const [comparaison, setComparaison] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    fpaApi.getCycles()
      .then((res) => setCycles(
        Array.isArray(res.data) ? res.data : (res.data?.results ?? [])))
      .catch(() => setError('Impossible de charger les cycles.'))
  }, [])

  useEffect(() => {
    if (!cycleId) return
    fpaApi.getScenarios({ cycle: cycleId })
      .then((res) => setScenarios(
        Array.isArray(res.data) ? res.data : (res.data?.results ?? [])))
      .catch(() => setError('Impossible de charger les scénarios.'))
  }, [cycleId])

  const toggle = (id) => {
    setSelection((prev) => (
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))
  }

  const comparer = async () => {
    setError(null)
    try {
      const res = await fpaApi.comparerScenarios({
        cycle: cycleId, scenarios: selection.join(','),
      })
      setComparaison(res.data)
    } catch {
      setError('La comparaison a échoué.')
    }
  }

  const promouvoir = async (id) => {
    setError(null)
    try {
      await fpaApi.promouvoirScenario(id)
      const res = await fpaApi.getScenarios({ cycle: cycleId })
      setScenarios(Array.isArray(res.data) ? res.data : (res.data?.results ?? []))
    } catch {
      setError('La promotion a échoué (droit FP&A/Directeur requis ?).')
    }
  }

  const base = useMemo(
    () => (comparaison ? Number(comparaison.base || 0) : 0), [comparaison])

  return (
    <div>
      <PageHeader
        title="Scénarios what-if"
        subtitle="Comparaison côte-à-côte et promotion en budget de base"
        actions={
          <Button onClick={comparer} disabled={!cycleId || selection.length === 0}>
            Comparer ({selection.length})
          </Button>
        }
      />
      <div style={{ marginBottom: 16 }}>
        <select
          aria-label="Cycle budgétaire"
          value={cycleId}
          onChange={(e) => { setCycleId(e.target.value); setSelection([]); setComparaison(null) }}
        >
          <option value="">— Cycle budgétaire —</option>
          {cycles.map((c) => <option key={c.id} value={c.id}>{c.nom}</option>)}
        </select>
      </div>
      {error && <p role="alert" style={{ color: 'var(--danger, #c00)' }}>{error}</p>}
      <Card>
        <ul style={{ listStyle: 'none', padding: 0 }}>
          {scenarios.map((s) => (
            <li key={s.id} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: 6 }}>
              <input
                type="checkbox"
                aria-label={`Sélectionner ${s.nom}`}
                checked={selection.includes(s.id)}
                onChange={() => toggle(s.id)}
              />
              <span style={{ flex: 1 }}>
                {s.nom}
                {s.est_scenario_base && (
                  <strong style={{ marginLeft: 8, fontSize: 12 }}>(base)</strong>
                )}
              </span>
              {!s.est_scenario_base && (
                <Button variant="ghost" onClick={() => promouvoir(s.id)}>
                  Promouvoir en base
                </Button>
              )}
            </li>
          ))}
        </ul>
      </Card>
      {comparaison && (
        <Card>
          <table style={{ borderCollapse: 'collapse', width: '100%' }}>
            <thead>
              <tr>
                <th style={{ textAlign: 'left', padding: 8 }}>Scénario</th>
                <th style={{ padding: 8 }}>Total</th>
                <th style={{ padding: 8 }}>Écart vs base</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td style={{ padding: 8, fontWeight: 700 }}>Budget de base</td>
                <td style={{ padding: 8 }}>{formatMAD(base)}</td>
                <td style={{ padding: 8 }}>—</td>
              </tr>
              {comparaison.scenarios.map((r) => (
                <tr key={r.id}>
                  <td style={{ padding: 8 }}>{r.nom}</td>
                  <td style={{ padding: 8 }}>{formatMAD(Number(r.total || 0))}</td>
                  <td style={{ padding: 8 }}>{formatMAD(Number(r.ecart || 0))}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  )
}
