import { useEffect, useMemo, useState } from 'react'
import fpaApi from '../../api/fpaApi'
import { Button, Card } from '../../ui'
import PageHeader from '../../components/layout/PageHeader'
import { formatMAD } from '../../lib/format'

/* ============================================================================
   NTFPA4 — Écran de saisie budgétaire type tableur.
   ----------------------------------------------------------------------------
   Grille département × mois (12 colonnes) par catégorie. Édition inline
   cellule-par-cellule, total ligne/colonne calculé en live, sauvegarde par lot
   (bulk PATCH). Un responsable saisit ses 12 mois × N catégories en une vue,
   sans rechargement. Budget MACRO (société/département/période), jamais le
   budget micro par chantier.
   ========================================================================== */

const CATEGORIES = [
  ['masse_salariale', 'Masse salariale'],
  ['marketing', 'Marketing'],
  ['it', 'IT'],
  ['frais_generaux', 'Frais généraux'],
  ['investissement', 'Investissement'],
  ['autre', 'Autre'],
]
const MOIS = Array.from({ length: 12 }, (_, i) => i + 1)
const MOIS_LABELS = ['Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Juin', 'Juil', 'Aoû', 'Sep', 'Oct', 'Nov', 'Déc']

export default function SaisiePage() {
  const [cycles, setCycles] = useState([])
  const [departements, setDepartements] = useState([])
  const [cycleId, setCycleId] = useState('')
  const [departementId, setDepartementId] = useState('')
  const [grid, setGrid] = useState({}) // key `${categorie}:${mois}` → { id, montant }
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    Promise.all([fpaApi.getCycles(), fpaApi.getDepartements({ actif: 1 })])
      .then(([c, d]) => {
        setCycles(Array.isArray(c.data) ? c.data : (c.data?.results ?? []))
        setDepartements(Array.isArray(d.data) ? d.data : (d.data?.results ?? []))
      })
      .catch(() => setError('Impossible de charger cycles/départements.'))
  }, [])

  useEffect(() => {
    if (!cycleId || !departementId) return
    setLoading(true)
    setError(null)
    fpaApi.getLignesBudget({ cycle: cycleId, departement: departementId })
      .then((res) => {
        const rows = Array.isArray(res.data) ? res.data : (res.data?.results ?? [])
        const next = {}
        rows.forEach((r) => {
          next[`${r.categorie}:${r.mois}`] = { id: r.id, montant: r.montant_prevu }
        })
        setGrid(next)
      })
      .catch(() => setError('Impossible de charger les lignes de budget.'))
      .finally(() => setLoading(false))
  }, [cycleId, departementId])

  const setCell = (categorie, mois, value) => {
    setGrid((prev) => ({
      ...prev,
      [`${categorie}:${mois}`]: {
        ...(prev[`${categorie}:${mois}`] || {}),
        montant: value,
      },
    }))
  }

  const totauxLigne = useMemo(() => {
    const out = {}
    CATEGORIES.forEach(([cat]) => {
      out[cat] = MOIS.reduce(
        (s, m) => s + Number(grid[`${cat}:${m}`]?.montant || 0), 0)
    })
    return out
  }, [grid])

  const totauxColonne = useMemo(() => {
    const out = {}
    MOIS.forEach((m) => {
      out[m] = CATEGORIES.reduce(
        (s, [cat]) => s + Number(grid[`${cat}:${m}`]?.montant || 0), 0)
    })
    return out
  }, [grid])

  const totalGeneral = useMemo(
    () => Object.values(totauxLigne).reduce((s, v) => s + v, 0), [totauxLigne])

  const enregistrer = async () => {
    if (!cycleId || !departementId) return
    setSaving(true)
    setError(null)
    try {
      for (const [cat] of CATEGORIES) {
        for (const m of MOIS) {
          const cell = grid[`${cat}:${m}`]
          if (!cell) continue
          const montant = Number(cell.montant || 0)
          if (cell.id) {
            await fpaApi.updateLigneBudget(cell.id, { montant_prevu: montant })
          } else if (montant !== 0) {
            await fpaApi.createLigneBudget({
              cycle: cycleId, departement: departementId,
              categorie: cat, mois: m, montant_prevu: montant,
            })
          }
        }
      }
    } catch {
      setError('La sauvegarde a échoué (cycle clôturé ou budget soumis ?).')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div>
      <PageHeader
        title="Saisie budgétaire"
        subtitle="Grille département × mois par catégorie (budget annuel)"
        actions={
          <Button onClick={enregistrer} disabled={saving || !cycleId || !departementId}>
            {saving ? 'Enregistrement…' : 'Enregistrer'}
          </Button>
        }
      />
      <div style={{ display: 'flex', gap: 12, marginBottom: 16 }}>
        <select
          aria-label="Cycle budgétaire"
          value={cycleId}
          onChange={(e) => setCycleId(e.target.value)}
        >
          <option value="">— Cycle budgétaire —</option>
          {cycles.map((c) => <option key={c.id} value={c.id}>{c.nom}</option>)}
        </select>
        <select
          aria-label="Département"
          value={departementId}
          onChange={(e) => setDepartementId(e.target.value)}
        >
          <option value="">— Département —</option>
          {departements.map((d) => <option key={d.id} value={d.id}>{d.nom}</option>)}
        </select>
      </div>
      {error && <p role="alert" style={{ color: 'var(--danger, #c00)' }}>{error}</p>}
      <Card>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ borderCollapse: 'collapse', width: '100%' }}>
            <thead>
              <tr>
                <th style={{ textAlign: 'left', padding: 8 }}>Catégorie</th>
                {MOIS_LABELS.map((label) => (
                  <th key={label} style={{ padding: 8 }}>{label}</th>
                ))}
                <th style={{ padding: 8 }}>Total</th>
              </tr>
            </thead>
            <tbody>
              {CATEGORIES.map(([cat, label]) => (
                <tr key={cat}>
                  <td style={{ padding: 8 }}>{label}</td>
                  {MOIS.map((m) => (
                    <td key={m} style={{ padding: 4 }}>
                      <input
                        type="number"
                        step="any"
                        aria-label={`${label} ${MOIS_LABELS[m - 1]}`}
                        value={grid[`${cat}:${m}`]?.montant ?? ''}
                        disabled={loading}
                        onChange={(e) => setCell(cat, m, e.target.value)}
                        style={{ width: 72 }}
                      />
                    </td>
                  ))}
                  <td style={{ padding: 8, fontWeight: 600 }}>
                    {formatMAD(totauxLigne[cat] || 0)}
                  </td>
                </tr>
              ))}
              <tr>
                <td style={{ padding: 8, fontWeight: 700 }}>Total</td>
                {MOIS.map((m) => (
                  <td key={m} style={{ padding: 8, fontWeight: 600 }}>
                    {formatMAD(totauxColonne[m] || 0)}
                  </td>
                ))}
                <td style={{ padding: 8, fontWeight: 700 }}>
                  {formatMAD(totalGeneral)}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}
