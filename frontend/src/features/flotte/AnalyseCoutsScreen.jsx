import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Tabs, TabsList, TabsTrigger, TabsContent, Segmented, Spinner, EmptyState,
  Badge, Button, toast,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Label, Input, confirmLeaveIfDirty,
} from '../../ui'
import { ListShell } from '../../ui/module'
import PageHeader from '../../components/layout/PageHeader'
import flotteApi from '../../api/flotteApi'
import useFlotteResource from './useFlotteResource'
import { formatMAD, formatNumber } from '../../lib/format'

/* ============================================================================
   XFLT7/15/18 — Analyse des coûts (`/flotte/analyse-couts`).
   ----------------------------------------------------------------------------
   Onglets : pivot des coûts (XFLT7, group_by véhicule/catégorie/mois/
   conducteur/garage/type de service + outliers de consommation), analyse de
   remplacement (XFLT15, règles 50/30/20), budget vs réalisé (XFLT18). Chiffres
   d'exploitation INTERNES — jamais des prix client, aucun prix d'achat/marge.
   ========================================================================== */

const GROUP_BY_OPTIONS = [
  { value: 'vehicule', label: 'Véhicule' },
  { value: 'categorie', label: 'Catégorie' },
  { value: 'mois', label: 'Mois' },
  { value: 'conducteur', label: 'Conducteur' },
  { value: 'garage', label: 'Garage' },
  { value: 'type_service', label: 'Type de service' },
]

// WIR46 — Catégories de coût (miroir fidèle de `CoutVehicule.Categorie`,
// backend/apps/flotte/models.py) : aucun consommateur d'écriture n'existait
// pour `CoutVehiculeViewSet` malgré un backend full CRUD.
const COUT_CATEGORIES = [
  { value: 'carburant', label: 'Carburant' },
  { value: 'entretien', label: 'Entretien' },
  { value: 'assurance', label: 'Assurance' },
  { value: 'vignette', label: 'Vignette' },
  { value: 'amende', label: 'Amende' },
  { value: 'peage', label: 'Péage' },
  { value: 'parking', label: 'Parking' },
  { value: 'lavage', label: 'Lavage' },
  { value: 'contrat', label: 'Contrat' },
  { value: 'autre', label: 'Autre' },
]

// WIR46 — Catégories budgétaires (miroir fidèle de `BudgetFlotte.Categorie`).
const BUDGET_CATEGORIES = [
  { value: 'carburant', label: 'Carburant' },
  { value: 'entretien', label: 'Entretien' },
  { value: 'assurance', label: 'Assurance' },
  { value: 'vignette', label: 'Vignette' },
  { value: 'contrat', label: 'Contrat' },
  { value: 'autre', label: 'Autre' },
]

// WIR46 — Dialogue de saisie d'un coût d'exploitation divers (péage/parking/
// lavage…) sur `CoutVehiculeViewSet` (full CRUD, aucun consommateur d'écriture).
function CoutVehiculeDialog({ actifs = [], onClose, onSaved }) {
  const [actifFlotte, setActifFlotte] = useState('')
  const [categorie, setCategorie] = useState('peage')
  const [date, setDate] = useState('')
  const [montant, setMontant] = useState('')
  const [fournisseur, setFournisseur] = useState('')
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)

  const peutEnregistrer = Boolean(actifFlotte && date && montant !== '')
  const dirty = Boolean(actifFlotte || date || montant || fournisseur || categorie !== 'peage')
  const closeIfConfirmed = () => { if (confirmLeaveIfDirty(dirty)) onClose?.() }

  const submit = async (e) => {
    e.preventDefault()
    if (!peutEnregistrer) return
    setSaving(true)
    setServerError(null)
    try {
      await flotteApi.couts.create({
        actif_flotte: Number(actifFlotte),
        categorie,
        date,
        montant: Number(montant),
        fournisseur,
      })
      onSaved?.()
    } catch (err) {
      const data = err?.response?.data
      setServerError(
        data?.montant
        || data?.detail
        || (typeof data === 'string' ? data : 'Enregistrement impossible.'),
      )
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) closeIfConfirmed() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Nouveau coût d’exploitation</DialogTitle>
        </DialogHeader>

        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="cout-actif">Actif (véhicule ou engin)</Label>
              <select
                id="cout-actif"
                autoFocus
                value={actifFlotte}
                onChange={(e) => setActifFlotte(e.target.value)}
                className="h-9 rounded-md border border-border bg-card px-3 text-sm"
              >
                <option value="">— Choisir —</option>
                {actifs.map((a) => (
                  <option key={a.id} value={a.id}>{a.label || `#${a.id}`}</option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="cout-categorie">Catégorie</Label>
              <select
                id="cout-categorie"
                value={categorie}
                onChange={(e) => setCategorie(e.target.value)}
                className="h-9 rounded-md border border-border bg-card px-3 text-sm"
              >
                {COUT_CATEGORIES.map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="cout-date">Date</Label>
              <Input id="cout-date" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="cout-montant">Montant (MAD)</Label>
              <Input id="cout-montant" type="number" step="any" value={montant} onChange={(e) => setMontant(e.target.value)} />
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="cout-fournisseur">Fournisseur (saisie libre)</Label>
            <Input id="cout-fournisseur" value={fournisseur} onChange={(e) => setFournisseur(e.target.value)} />
          </div>

          {serverError && (
            <p className="text-sm text-destructive" role="alert">{serverError}</p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={closeIfConfirmed}>Annuler</Button>
            <Button type="submit" disabled={!peutEnregistrer || saving}>
              {saving ? 'Enregistrement…' : 'Créer'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

// WIR46 — Dialogue de saisie du budget flotte annuel par catégorie
// (`BudgetFlotteViewSet`, full CRUD sans consommateur d'écriture — « Budgété »
// restait toujours à 0).
function BudgetFlotteDialog({ anneeParDefaut, onClose, onSaved }) {
  const [annee, setAnnee] = useState(String(anneeParDefaut))
  const [categorie, setCategorie] = useState('carburant')
  const [montantBudgete, setMontantBudgete] = useState('')
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)

  const peutEnregistrer = Boolean(annee && montantBudgete !== '')
  const dirty = Boolean(montantBudgete || categorie !== 'carburant' || annee !== String(anneeParDefaut))
  const closeIfConfirmed = () => { if (confirmLeaveIfDirty(dirty)) onClose?.() }

  const submit = async (e) => {
    e.preventDefault()
    if (!peutEnregistrer) return
    setSaving(true)
    setServerError(null)
    try {
      await flotteApi.budgets.create({
        annee: Number(annee),
        categorie,
        montant_budgete: Number(montantBudgete),
      })
      onSaved?.()
    } catch (err) {
      const data = err?.response?.data
      setServerError(
        data?.montant_budgete
        || data?.non_field_errors?.[0]
        || data?.detail
        || (typeof data === 'string' ? data : 'Enregistrement impossible.'),
      )
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) closeIfConfirmed() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Nouvelle ligne budgétaire</DialogTitle>
        </DialogHeader>

        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="budget-annee">Année</Label>
              <Input id="budget-annee" type="number" step="1" autoFocus value={annee} onChange={(e) => setAnnee(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="budget-categorie">Catégorie</Label>
              <select
                id="budget-categorie"
                value={categorie}
                onChange={(e) => setCategorie(e.target.value)}
                className="h-9 rounded-md border border-border bg-card px-3 text-sm"
              >
                {BUDGET_CATEGORIES.map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="budget-montant">Montant budgété (MAD)</Label>
            <Input id="budget-montant" type="number" step="any" value={montantBudgete} onChange={(e) => setMontantBudgete(e.target.value)} />
          </div>

          {serverError && (
            <p className="text-sm text-destructive" role="alert">{serverError}</p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={closeIfConfirmed}>Annuler</Button>
            <Button type="submit" disabled={!peutEnregistrer || saving}>
              {saving ? 'Enregistrement…' : 'Créer'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function PivotTab() {
  const [groupBy, setGroupBy] = useState('vehicule')
  const [state, setState] = useState({ loading: true, error: null, data: null })
  const [showForm, setShowForm] = useState(false)
  const { data: actifs } = useFlotteResource(flotteApi.actifs.list, {})

  const load = useCallback(() => {
    let cancelled = false
    setState({ loading: true, error: null, data: null })
    flotteApi.rapportCouts({ group_by: groupBy })
      .then((res) => { if (!cancelled) setState({ loading: false, error: null, data: res?.data || null }) })
      .catch((err) => {
        if (!cancelled) setState({ loading: false, error: err?.response?.data?.detail || 'Rapport indisponible.', data: null })
      })
    return () => { cancelled = true }
  }, [groupBy])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { load() }, [load])

  const pivotColumns = useMemo(() => [
    { id: 'libelle', header: 'Clé', width: 220, accessor: (r) => r.libelle, cell: (v) => v || '—' },
    {
      id: 'total', header: 'Total', align: 'right', numeric: true, width: 150, searchable: false,
      accessor: (r) => Number(r.total ?? 0),
      cell: (v) => formatMAD(v, { decimals: 0 }),
    },
  ], [])

  const outlierColumns = useMemo(() => [
    { id: 'label', header: 'Véhicule', width: 180, accessor: (r) => r.label, cell: (v) => v || '—' },
    { id: 'conso', header: 'Consommation', align: 'right', numeric: true, width: 140, searchable: false, accessor: (r) => r.conso, cell: (v) => (v != null ? formatNumber(v, { decimals: 1 }) : '—') },
    { id: 'mediane_modele', header: 'Médiane modèle', align: 'right', numeric: true, width: 150, searchable: false, accessor: (r) => r.mediane_modele, cell: (v) => (v != null ? formatNumber(v, { decimals: 1 }) : '—') },
    { id: 'ecart_pct', header: 'Écart', align: 'right', numeric: true, width: 100, searchable: false, accessor: (r) => r.ecart_pct, cell: (v) => (v != null ? `+${formatNumber(v, { decimals: 0 })} %` : '—') },
  ], [])

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Segmented options={GROUP_BY_OPTIONS} value={groupBy} onChange={setGroupBy} aria-label="Regrouper par" />
        <Button onClick={() => setShowForm(true)}>Nouveau coût</Button>
      </div>
      {state.loading ? (
        <div className="flex items-center gap-2 py-6 text-sm text-muted-foreground"><Spinner className="size-4" /> Chargement…</div>
      ) : state.error ? (
        <EmptyState title="Indisponible" description={state.error} />
      ) : (
        <>
          <ListShell
            title="Pivot des coûts"
            subtitle="Coûts d’exploitation internes, jamais des prix client."
            columns={pivotColumns}
            rows={state.data?.pivot || []}
            exportName="analyse-couts-pivot"
            emptyTitle="Aucune donnée"
            emptyDescription="Aucun coût enregistré pour ce regroupement."
          />
          {state.data?.outliers?.length > 0 && (
            <ListShell
              title="Outliers de consommation"
              subtitle="Véhicules dont la consommation dépasse de plus de 20 % la médiane de leur modèle."
              columns={outlierColumns}
              rows={state.data.outliers}
              exportName="analyse-couts-outliers"
              emptyTitle="Aucun outlier"
              emptyDescription="Aucun véhicule hors norme."
            />
          )}
        </>
      )}
      {showForm && (
        <CoutVehiculeDialog
          actifs={actifs}
          onClose={() => setShowForm(false)}
          onSaved={() => { setShowForm(false); load(); toast.success('Coût enregistré.') }}
        />
      )}
    </div>
  )
}

function RemplacementTab() {
  const [state, setState] = useState({ loading: true, error: null, data: null })

  const load = useCallback(() => {
    let cancelled = false
    setState({ loading: true, error: null, data: null })
    flotteApi.rapportRemplacement()
      .then((res) => { if (!cancelled) setState({ loading: false, error: null, data: res?.data || null }) })
      .catch((err) => {
        if (!cancelled) setState({ loading: false, error: err?.response?.data?.detail || 'Rapport indisponible.', data: null })
      })
    return () => { cancelled = true }
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { load() }, [load])

  const columns = useMemo(() => [
    { id: 'immatriculation', header: 'Immatriculation', width: 150, accessor: (r) => r.immatriculation, cell: (v) => v || '—' },
    { id: 'age_ans', header: 'Âge (ans)', align: 'right', numeric: true, width: 100, accessor: (r) => r.age_ans, cell: (v) => (v != null ? v : '—') },
    { id: 'kilometrage', header: 'Km', align: 'right', numeric: true, width: 120, searchable: false, accessor: (r) => r.kilometrage, cell: (v) => (v != null ? `${formatNumber(v)} km` : '—') },
    { id: 'nb_regles', header: 'Règles déclenchées', align: 'right', numeric: true, width: 150, searchable: false, accessor: (r) => r.nb_regles, cell: (v) => v ?? 0 },
    {
      id: 'budget_remplacement_estime', header: 'Budget estimé', align: 'right', numeric: true, width: 150, searchable: false,
      accessor: (r) => Number(r.budget_remplacement_estime ?? 0),
      cell: (v) => (v ? formatMAD(v, { decimals: 0 }) : '—'),
    },
    {
      id: 'a_remplacer', header: 'À remplacer', width: 120, searchable: false,
      accessor: (r) => (r.a_remplacer ? 'Oui' : ''),
      cell: (_v, r) => (r.a_remplacer ? <Badge tone="danger">À remplacer</Badge> : <span className="text-muted-foreground">—</span>),
    },
  ], [])

  if (state.loading) {
    return <div className="flex items-center gap-2 py-6 text-sm text-muted-foreground"><Spinner className="size-4" /> Chargement…</div>
  }
  if (state.error) {
    return <EmptyState title="Indisponible" description={state.error} />
  }

  return (
    <div className="flex flex-col gap-4">
      {state.data?.budget_annuel_estime != null && (
        <p className="text-sm text-muted-foreground">
          Budget annuel estimé de remplacement : <strong>{formatMAD(state.data.budget_annuel_estime, { decimals: 0 })}</strong>
        </p>
      )}
      <ListShell
        title="Fin de vie économique"
        subtitle="Âge, kilométrage et ratio coût-réparation/valeur vénale (règle 50/30/20)."
        columns={columns}
        rows={state.data?.vehicules || []}
        exportName="analyse-remplacement"
        emptyTitle="Aucun véhicule"
        emptyDescription="Aucun véhicule actif à évaluer."
      />
    </div>
  )
}

function BudgetTab() {
  const [annee, setAnnee] = useState(new Date().getFullYear())
  const [state, setState] = useState({ loading: true, error: null, data: null })
  const [showForm, setShowForm] = useState(false)

  const load = useCallback(() => {
    let cancelled = false
    setState({ loading: true, error: null, data: null })
    flotteApi.rapportBudget({ annee })
      .then((res) => { if (!cancelled) setState({ loading: false, error: null, data: res?.data || null }) })
      .catch((err) => {
        if (!cancelled) setState({ loading: false, error: err?.response?.data?.detail || 'Rapport indisponible.', data: null })
      })
    return () => { cancelled = true }
  }, [annee])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { load() }, [load])

  const columns = useMemo(() => [
    { id: 'categorie_display', header: 'Catégorie', width: 160, accessor: (r) => r.categorie_display, cell: (v) => v || '—' },
    { id: 'budgete', header: 'Budgété', align: 'right', numeric: true, width: 140, searchable: false, accessor: (r) => Number(r.budgete ?? 0), cell: (v) => formatMAD(v, { decimals: 0 }) },
    { id: 'realise', header: 'Réalisé', align: 'right', numeric: true, width: 140, searchable: false, accessor: (r) => Number(r.realise ?? 0), cell: (v) => formatMAD(v, { decimals: 0 }) },
    { id: 'pct', header: '%', align: 'right', numeric: true, width: 100, searchable: false, accessor: (r) => r.pct, cell: (v) => (v != null ? `${formatNumber(v, { decimals: 0 })} %` : '—') },
    {
      id: 'niveau', header: 'Niveau', width: 110, searchable: false, accessor: (r) => r.niveau,
      cell: (v) => {
        if (v === 'rouge') return <Badge tone="danger">Dépassé</Badge>
        if (v === 'orange') return <Badge tone="warning">Sous surveillance</Badge>
        if (v === 'ok') return <Badge tone="success">OK</Badge>
        return <span className="text-muted-foreground">—</span>
      },
    },
  ], [])

  const years = useMemo(() => {
    const current = new Date().getFullYear()
    return Array.from({ length: 4 }, (_, i) => current - i)
  }, [])

  if (state.loading) {
    return <div className="flex items-center gap-2 py-6 text-sm text-muted-foreground"><Spinner className="size-4" /> Chargement…</div>
  }
  if (state.error) {
    return <EmptyState title="Indisponible" description={state.error} />
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Segmented
          options={years.map((y) => ({ value: String(y), label: String(y) }))}
          value={String(annee)}
          onChange={(v) => setAnnee(Number(v))}
          aria-label="Année"
        />
        <Button onClick={() => setShowForm(true)}>Nouveau budget</Button>
      </div>
      <ListShell
        title={`Budget flotte ${annee} — vs réalisé`}
        columns={columns}
        rows={state.data?.categories || []}
        exportName={`budget-flotte-${annee}`}
        emptyTitle="Aucune catégorie"
        emptyDescription="Aucune ligne budgétaire."
      />
      {showForm && (
        <BudgetFlotteDialog
          anneeParDefaut={annee}
          onClose={() => setShowForm(false)}
          onSaved={() => { setShowForm(false); load(); toast.success('Ligne budgétaire créée.') }}
        />
      )}
    </div>
  )
}

export default function AnalyseCoutsScreen() {
  return (
    <div className="page flex flex-col gap-4">
      <PageHeader
        title="Analyse des coûts"
        subtitle="Pivot des coûts, fin de vie économique et budget vs réalisé — jamais de prix d’achat/marge."
      />
      <Tabs defaultValue="pivot">
        <TabsList className="flex-wrap">
          <TabsTrigger value="pivot">Pivot des coûts</TabsTrigger>
          <TabsTrigger value="remplacement">Remplacement</TabsTrigger>
          <TabsTrigger value="budget">Budget vs réalisé</TabsTrigger>
        </TabsList>
        <TabsContent value="pivot"><PivotTab /></TabsContent>
        <TabsContent value="remplacement"><RemplacementTab /></TabsContent>
        <TabsContent value="budget"><BudgetTab /></TabsContent>
      </Tabs>
    </div>
  )
}
