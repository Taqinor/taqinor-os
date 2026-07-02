import { useCallback, useEffect, useMemo, useState } from 'react'
import { Wallet } from 'lucide-react'
import {
  Card, Button, Spinner, EmptyState, Badge, DataTable,
} from '../../../ui'
import { BarArrondie } from '../../../ui/charts'
import { formatMAD } from '../../../lib/format'
import gestionProjetApi from '../../../api/gestionProjetApi'
import { errMessage, StatutBudget, CATEGORIES_BUDGET } from '../constants'
import ProjetPicker from '../components/ProjetPicker'

/* UX41 — Budget & P&L : budgets par catégorie, réel vs budgété (recharts),
   coûts engagés vs réels. Toutes les données sont INTERNES (jamais client). */

const CAT_LABEL = Object.fromEntries(CATEGORIES_BUDGET.map((c) => [c.value, c.label]))

export default function BudgetPage() {
  const [projetId, setProjetId] = useState('')
  const [budgets, setBudgets] = useState([])
  const [lignes, setLignes] = useState([])
  const [coutsReels, setCoutsReels] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const asList = (r) => (Array.isArray(r.data) ? r.data : r.data?.results ?? [])

  const load = useCallback(async (pid) => {
    if (!pid) { setBudgets([]); setLignes([]); setCoutsReels(null); return }
    setLoading(true)
    setError(null)
    try {
      const bRes = await gestionProjetApi.getBudgets({ projet: pid })
      const bs = asList(bRes)
      setBudgets(bs)
      const budgetRef = bs.find((b) => b.statut === 'valide') ?? bs[0]
      const [lRes, cRes] = await Promise.all([
        budgetRef ? gestionProjetApi.getLignesBudget({ budget: budgetRef.id }) : Promise.resolve({ data: [] }),
        gestionProjetApi.getProjetCoutsEngagesReels(pid).catch(() => ({ data: null })),
      ])
      setLignes(asList(lRes))
      setCoutsReels(cRes.data)
    } catch (err) {
      setError(errMessage(err, 'Chargement du budget impossible.'))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    let alive = true
    ;(async () => { if (alive) await load(projetId) })()
    return () => { alive = false }
  }, [projetId, load])

  // Budget par catégorie (somme des lignes).
  const parCategorie = useMemo(() => {
    const acc = {}
    for (const l of lignes) {
      acc[l.categorie] = (acc[l.categorie] ?? 0) + Number(l.montant_prevu ?? 0)
    }
    return acc
  }, [lignes])

  // Graphique budgété vs réel par catégorie (deux barres par catégorie).
  const chartData = useMemo(() => {
    const reelByCat = {}
    for (const c of coutsReels?.par_categorie ?? []) {
      reelByCat[c.categorie] = Number(c.reel ?? 0)
    }
    const cats = new Set([...Object.keys(parCategorie), ...Object.keys(reelByCat)])
    const bars = []
    for (const cat of cats) {
      const lbl = CAT_LABEL[cat] ?? cat
      bars.push({ label: `${lbl} · budget`, value: parCategorie[cat] ?? 0, color: 'muted-foreground' })
      const reel = reelByCat[cat] ?? 0
      const budget = parCategorie[cat] ?? 0
      bars.push({ label: `${lbl} · réel`, value: reel, color: reel > budget ? 'destructive' : 'primary' })
    }
    return bars
  }, [parCategorie, coutsReels])

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-display text-xl font-semibold tracking-tight">Budget & P&L</h1>
          <p className="text-sm text-muted-foreground">Budget par catégorie, réel vs budgété, coûts engagés (interne).</p>
        </div>
        <ProjetPicker value={projetId} onChange={setProjetId} />
      </div>

      {!projetId ? (
        <EmptyState icon={Wallet} title="Aucun projet sélectionné" description="Choisissez un projet pour piloter son budget." />
      ) : loading ? (
        <div className="flex justify-center p-10"><Spinner /></div>
      ) : error ? (
        <EmptyState title="Erreur" description={error} action={<Button variant="outline" onClick={() => load(projetId)}>Réessayer</Button>} />
      ) : (
        <>
          <Card className="p-4 sm:p-5">
            <h3 className="mb-2 font-display text-base font-semibold">Budgets du projet</h3>
            {budgets.length ? (
              <ul className="flex flex-col gap-1 text-sm">
                {budgets.map((b) => (
                  <li key={b.id} className="flex flex-wrap items-center gap-2">
                    <span className="font-medium">{b.libelle || `Budget v${b.version}`}</span>
                    <StatutBudget status={b.statut} />
                    <span className="ml-auto font-medium">{formatMAD(b.total?.total ?? 0)}</span>
                  </li>
                ))}
              </ul>
            ) : <p className="text-sm text-muted-foreground">Aucun budget défini pour ce projet.</p>}
          </Card>

          <Card className="p-4 sm:p-5">
            <h3 className="mb-3 font-display text-base font-semibold">Réel vs budgété par catégorie</h3>
            {chartData.length ? (
              <BarArrondie
                data={chartData}
                layout="vertical"
                categoryWidth={150}
                height={Math.max(200, chartData.length * 26)}
                name="Montant"
                tooltipFormat={(v) => formatMAD(v)}
              />
            ) : <EmptyState title="Aucune ligne de budget" description="Ajoutez des lignes de budget pour comparer au réel." />}
          </Card>

          {coutsReels && (
            <Card className="p-4 sm:p-5">
              <h3 className="mb-3 font-display text-base font-semibold">Engagé vs réel</h3>
              <DataTable
                data={coutsReels.par_categorie ?? []}
                getRowId={(c) => c.categorie}
                searchable={false}
                columns={[
                  { id: 'cat', header: 'Catégorie', accessor: (c) => CAT_LABEL[c.categorie] ?? c.categorie },
                  { id: 'budget', header: 'Budget', align: 'right', numeric: true, accessor: (c) => Number(c.budget ?? 0), cell: (v) => formatMAD(v) },
                  { id: 'reel', header: 'Réel', align: 'right', numeric: true, accessor: (c) => Number(c.reel ?? 0), cell: (v) => formatMAD(v) },
                  {
                    id: 'ecart', header: 'Écart', align: 'right', numeric: true,
                    accessor: (c) => Number(c.ecart ?? 0),
                    cell: (v) => <span className={v < 0 ? 'text-destructive' : 'text-foreground'}>{formatMAD(v)}</span>,
                  },
                  {
                    id: 'ecart_pct', header: 'Écart %', align: 'right', numeric: true,
                    accessor: (c) => (c.ecart_pct == null ? null : Number(c.ecart_pct)),
                    cell: (v) => (v == null ? '—' : `${v} %`),
                  },
                ]}
                emptyTitle="Aucune donnée"
                emptyDescription="Aucun coût engagé pour ce projet."
              />
              {coutsReels.total && (
                <div className="mt-3 flex flex-wrap gap-4 border-t border-border pt-3 text-sm">
                  <span>Total budget : <strong>{formatMAD(coutsReels.total.budget)}</strong></span>
                  <span>Total réel : <strong>{formatMAD(coutsReels.total.reel)}</strong></span>
                  <span>Écart : <strong>{formatMAD(coutsReels.total.ecart)}</strong></span>
                </div>
              )}
              {coutsReels.nb_liens_depense != null && (
                <p className="mt-2 text-xs text-muted-foreground">
                  <Badge tone="neutral">{coutsReels.nb_liens_depense} liens de dépense</Badge>
                  {' '}Le réel matériel/sous-traitance dégrade proprement tant qu'aucune source cross-app n'est branchée.
                </p>
              )}
            </Card>
          )}
        </>
      )}
    </div>
  )
}
