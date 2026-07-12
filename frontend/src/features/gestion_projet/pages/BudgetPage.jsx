import { useCallback, useEffect, useMemo, useState } from 'react'
import { Wallet, Plus } from 'lucide-react'
import {
  Card, Button, Spinner, EmptyState, Badge, DataTable, Input, Label,
  Textarea, toast,
} from '../../../ui'
import { BarArrondie } from '../../../ui/charts'
import { formatMAD, formatDate, nbsp } from '../../../lib/format'
import gestionProjetApi from '../../../api/gestionProjetApi'
import { errMessage, StatutBudget, CATEGORIES_BUDGET, SanteRAG } from '../constants'
import ProjetPicker from '../components/ProjetPicker'
import BurndownChart from '../components/BurndownChart'
import { ResponsiveDialog } from '../../../ui/ResponsiveDialog'

/* UX41 — Budget & P&L : budgets par catégorie, réel vs budgété (recharts),
   coûts engagés vs réels. Toutes les données sont INTERNES (jamais client). */

const CAT_LABEL = Object.fromEntries(CATEGORIES_BUDGET.map((c) => [c.value, c.label]))

function todayISO(offset = 0) {
  const d = new Date()
  d.setDate(d.getDate() + offset)
  return d.toISOString().slice(0, 10)
}

export default function BudgetPage() {
  const [projetId, setProjetId] = useState('')
  const [budgets, setBudgets] = useState([])
  const [lignes, setLignes] = useState([])
  const [coutsReels, setCoutsReels] = useState(null)
  const [previsionFin, setPrevisionFin] = useState(null)
  const [burndown, setBurndown] = useState(null)
  const [points, setPoints] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [showPointForm, setShowPointForm] = useState(false)

  const asList = (r) => (Array.isArray(r.data) ? r.data : r.data?.results ?? [])

  const load = useCallback(async (pid) => {
    if (!pid) {
      setBudgets([]); setLignes([]); setCoutsReels(null)
      setPrevisionFin(null); setBurndown(null); setPoints([])
      return
    }
    setLoading(true)
    setError(null)
    try {
      const bRes = await gestionProjetApi.getBudgets({ projet: pid })
      const bs = asList(bRes)
      setBudgets(bs)
      const budgetRef = bs.find((b) => b.statut === 'valide') ?? bs[0]
      const [lRes, cRes, pfRes, bdRes, ptRes] = await Promise.all([
        budgetRef ? gestionProjetApi.getLignesBudget({ budget: budgetRef.id }) : Promise.resolve({ data: [] }),
        gestionProjetApi.getProjetCoutsEngagesReels(pid).catch(() => ({ data: null })),
        gestionProjetApi.getPrevisionFin(pid).catch(() => ({ data: null })),
        gestionProjetApi.getBurndown(pid, { debut: todayISO(-90), fin: todayISO(30) }).catch(() => ({ data: null })),
        gestionProjetApi.getPointsAvancement({ projet: pid }).catch(() => ({ data: [] })),
      ])
      setLignes(asList(lRes))
      setCoutsReels(cRes.data)
      setPrevisionFin(pfRes.data)
      setBurndown(bdRes.data)
      setPoints(asList(ptRes))
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
                  <span>{nbsp('Total budget :')} <strong>{formatMAD(coutsReels.total.budget)}</strong></span>
                  <span>{nbsp('Total réel :')} <strong>{formatMAD(coutsReels.total.reel)}</strong></span>
                  <span>{nbsp('Écart :')} <strong>{formatMAD(coutsReels.total.ecart)}</strong></span>
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

          {/* XPRJ16 — Prévision fin de projet (ETC/EAC), pilotage interne uniquement. */}
          {previsionFin && (
            <Card className="p-4 sm:p-5">
              <h3 className="mb-3 font-display text-base font-semibold">Prévision fin de projet (ETC/EAC)</h3>
              <DataTable
                data={previsionFin.par_categorie ?? []}
                getRowId={(c) => c.categorie}
                searchable={false}
                columns={[
                  { id: 'cat', header: 'Catégorie', accessor: (c) => CAT_LABEL[c.categorie] ?? c.categorie },
                  { id: 'budget', header: 'Budget', align: 'right', numeric: true, accessor: (c) => Number(c.budget ?? 0), cell: (v) => formatMAD(v) },
                  { id: 'reel', header: 'Réel', align: 'right', numeric: true, accessor: (c) => Number(c.reel ?? 0), cell: (v) => formatMAD(v) },
                  { id: 'etc', header: 'ETC', align: 'right', numeric: true, accessor: (c) => Number(c.etc ?? 0), cell: (v) => formatMAD(v) },
                  { id: 'eac', header: 'EAC', align: 'right', numeric: true, accessor: (c) => Number(c.eac ?? 0), cell: (v) => formatMAD(v) },
                  {
                    id: 'ecart', header: 'Écart EAC/Budget', align: 'right', numeric: true,
                    accessor: (c) => Number(c.ecart_eac_budget ?? 0),
                    cell: (v) => <span className={v < 0 ? 'text-destructive' : 'text-foreground'}>{formatMAD(v)}</span>,
                  },
                ]}
                emptyTitle="Aucune donnée"
              />
              <div className="mt-3 flex flex-wrap gap-4 border-t border-border pt-3 text-sm">
                {previsionFin.cpi && <span>CPI : <strong>{previsionFin.cpi}</strong></span>}
                <span>EAC total : <strong>{formatMAD(previsionFin.eac_total)}</strong></span>
                <span>Écart EAC/Budget : <strong>{formatMAD(previsionFin.ecart_eac_budget_total)}</strong></span>
              </div>
            </Card>
          )}

          {/* XPRJ17 — Burndown : charge restante vs ligne idéale. */}
          {burndown && (burndown.points ?? []).length > 0 && (
            <Card className="p-4 sm:p-5">
              <h3 className="mb-3 font-display text-base font-semibold">Burndown</h3>
              <BurndownChart points={burndown.points} />
            </Card>
          )}

          {/* XPRJ15 — Points d'avancement périodiques (statut RAG). */}
          <Card className="p-4 sm:p-5">
            <div className="mb-3 flex items-center justify-between">
              <h3 className="font-display text-base font-semibold">Points d'avancement (RAG)</h3>
              <Button size="sm" variant="outline" onClick={() => setShowPointForm(true)}>
                <Plus /> Nouveau point
              </Button>
            </div>
            {points.length ? (
              <ul className="flex flex-col gap-2">
                {points.map((p) => (
                  <li key={p.id} className="rounded-md border border-border p-3 text-sm">
                    <div className="flex flex-wrap items-center gap-2">
                      <SanteRAG status={p.sante} />
                      <span className="font-medium">{p.avancement_pct}%</span>
                      <span className="ml-auto text-xs text-muted-foreground">{p.date_point ? formatDate(p.date_point) : ''}</span>
                    </div>
                    {p.realisations && <p className="mt-1 text-xs text-muted-foreground">Réalisations : {p.realisations}</p>}
                    {p.risques && <p className="mt-1 text-xs text-muted-foreground">Risques : {p.risques}</p>}
                  </li>
                ))}
              </ul>
            ) : <EmptyState title="Aucun point d'avancement" description="Enregistrez un premier point RAG pour ce projet." />}
          </Card>
        </>
      )}

      {showPointForm && (
        <PointAvancementDialog
          projetId={projetId}
          onClose={() => setShowPointForm(false)}
          onSaved={(p) => { setShowPointForm(false); setPoints((rows) => [p, ...rows]); toast.success('Point d\'avancement enregistré.') }}
        />
      )}
    </div>
  )
}

function PointAvancementDialog({ projetId, onClose, onSaved }) {
  const [sante, setSante] = useState('vert')
  const [avancement, setAvancement] = useState('')
  const [realisations, setRealisations] = useState('')
  const [risques, setRisques] = useState('')
  const [saving, setSaving] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    if (avancement === '') {
      toast.error("L'avancement (%) est obligatoire.")
      return
    }
    setSaving(true)
    try {
      const res = await gestionProjetApi.createPointAvancement({
        projet: projetId,
        sante,
        avancement_pct: avancement,
        realisations,
        risques,
      })
      onSaved?.(res.data)
    } catch (err) {
      toast.error(errMessage(err, 'Enregistrement impossible.'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <ResponsiveDialog
      open
      onOpenChange={(o) => { if (!o) onClose?.() }}
      title="Nouveau point d'avancement"
    >
      <form onSubmit={submit} noValidate className="flex flex-col gap-3">
        <div className="flex flex-col gap-1">
          <Label htmlFor="pa-sante">Statut RAG</Label>
          <select
            id="pa-sante"
            className="h-9 rounded-md border border-input bg-background px-3 text-sm shadow-sm"
            value={sante}
            onChange={(e) => setSante(e.target.value)}
          >
            <option value="vert">Vert</option>
            <option value="orange">Orange</option>
            <option value="rouge">Rouge</option>
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <Label htmlFor="pa-avancement">Avancement (%)</Label>
          <Input id="pa-avancement" type="number" min="0" max="100" step="any" value={avancement} onChange={(e) => setAvancement(e.target.value)} />
        </div>
        <div className="flex flex-col gap-1">
          <Label htmlFor="pa-realisations">Réalisations</Label>
          <Textarea id="pa-realisations" rows={2} value={realisations} onChange={(e) => setRealisations(e.target.value)} />
        </div>
        <div className="flex flex-col gap-1">
          <Label htmlFor="pa-risques">Risques</Label>
          <Textarea id="pa-risques" rows={2} value={risques} onChange={(e) => setRisques(e.target.value)} />
        </div>
        <div className="mt-2 flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
          <Button type="submit" disabled={saving}>{saving ? 'Enregistrement…' : 'Enregistrer'}</Button>
        </div>
      </form>
    </ResponsiveDialog>
  )
}
