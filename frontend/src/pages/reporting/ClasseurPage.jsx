import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { RefreshCw, Save } from 'lucide-react'
import reportingApi from '../../api/reportingApi'
import { Button, Input, Spinner } from '../../ui'
import { toast } from '../../ui/confirm'
import PageHeader from '../../components/layout/PageHeader'

/* ============================================================================
   XPLT22 — Classeur léger embarqué avec données live (mini-spreadsheet BI).
   ----------------------------------------------------------------------------
   Grille de cellules (`reporting/classeurs/<id>/`) : chaque cellule porte soit
   une `valeur` littérale soit une `formule` (`=SOMME(A1:A3)`, `=A1+B1`…),
   évaluée AST-sûr côté serveur (`core.formula`, jamais `eval`). Les plages
   LIÉES à une `core.SavedQuery` (`liens`) sont ré-exécutées au chargement
   avec les droits du LECTEUR courant. `rafraichir/` recalcule tout ; `evaluer/`
   prévisualise une formule ad-hoc sans la persister.
   ========================================================================== */

const COLS = ['A', 'B', 'C', 'D', 'E', 'F']
const ROWS = Array.from({ length: 12 }, (_, i) => i + 1)

function cellRawValue(cell) {
  if (!cell) return ''
  if ('formule' in cell && cell.formule) return cell.formule
  if ('valeur' in cell) return String(cell.valeur ?? '')
  return ''
}

export default function ClasseurPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [classeur, setClasseur] = useState(null)
  const [loading, setLoading] = useState(true)
  const [resolved, setResolved] = useState({})
  const [saving, setSaving] = useState(false)

  const cellules = classeur?.cellules || {}

  const reload = () => reportingApi.getClasseur(id)
    .then((r) => setClasseur(r.data))
    .catch(() => toast.error('Classeur introuvable.'))

  useEffect(() => {
    let active = true
    reportingApi.getClasseur(id)
      .then((r) => { if (active) setClasseur(r.data) })
      .catch(() => { if (active) toast.error('Classeur introuvable.') })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [id])

  const rafraichir = () => {
    reportingApi.rafraichirClasseur(id)
      .then((r) => setResolved(r.data?.cellules || {}))
      .catch(() => toast.error('Rafraîchissement impossible.'))
  }

  const editCell = (ref, raw) => {
    setClasseur((c) => {
      if (!c) return c
      const next = { ...(c.cellules || {}) }
      if (raw.trim().startsWith('=')) {
        next[ref] = { formule: raw }
      } else if (raw.trim() === '') {
        delete next[ref]
      } else {
        const num = Number(raw)
        next[ref] = { valeur: Number.isNaN(num) ? raw : num }
      }
      return { ...c, cellules: next }
    })
  }

  const enregistrer = () => {
    setSaving(true)
    reportingApi.updateClasseur(id, { cellules })
      .then(() => {
        toast.success('Classeur enregistré.')
        reload()
        rafraichir()
      })
      .catch(() => toast.error('Enregistrement impossible.'))
      .finally(() => setSaving(false))
  }

  const grid = useMemo(() => {
    const rows = []
    for (const r of ROWS) {
      const cols = []
      for (const c of COLS) {
        const ref = `${c}${r}`
        cols.push(ref)
      }
      rows.push(cols)
    }
    return rows
  }, [])

  if (loading) {
    return <p className="flex items-center gap-2 py-10 text-sm text-muted-foreground"><Spinner /> Chargement…</p>
  }

  if (!classeur) {
    return (
      <div className="page">
        <p className="text-sm text-muted-foreground">Classeur introuvable.</p>
        <Button variant="secondary" onClick={() => navigate('/reporting')}>Retour</Button>
      </div>
    )
  }

  return (
    <div className="page">
      <PageHeader
        title={classeur.titre || 'Classeur'}
        subtitle="Mini-tableur BI — formules =SOMME(...) et plages liées à des requêtes sauvegardées, recalculées à chaque chargement."
      />

      <div className="mb-4 flex flex-wrap gap-2">
        <Button variant="secondary" onClick={rafraichir} data-testid="classeur-rafraichir">
          <RefreshCw /> Rafraîchir
        </Button>
        <Button onClick={enregistrer} loading={saving} data-testid="classeur-enregistrer">
          <Save /> Enregistrer
        </Button>
      </div>

      <div className="overflow-x-auto rounded-md border border-border" data-testid="classeur-grid">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr>
              <th className="w-10 border border-border bg-muted/40" />
              {COLS.map((c) => (
                <th key={c} className="border border-border bg-muted/40 px-2 py-1 text-xs font-semibold text-muted-foreground">
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {grid.map((rowRefs, rIdx) => (
              <tr key={ROWS[rIdx]}>
                <td className="border border-border bg-muted/40 px-2 py-1 text-center text-xs font-semibold text-muted-foreground">
                  {ROWS[rIdx]}
                </td>
                {rowRefs.map((ref) => (
                  <td key={ref} className="border border-border p-0">
                    <Input
                      aria-label={`Cellule ${ref}`}
                      className="h-8 rounded-none border-0 text-xs"
                      value={cellRawValue(cellules[ref])}
                      onChange={(e) => editCell(ref, e.target.value)}
                      title={resolved[ref] != null ? `= ${resolved[ref]}` : undefined}
                    />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {Object.keys(resolved).length > 0 && (
        <p className="mt-3 text-xs text-muted-foreground">
          Valeurs résolues (survol d’une cellule pour son résultat calculé).
        </p>
      )}
    </div>
  )
}
