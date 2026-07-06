import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Tabs, TabsList, TabsTrigger, TabsContent, Segmented, Spinner, EmptyState,
  Badge,
} from '../../ui'
import { ListShell } from '../../ui/module'
import PageHeader from '../../components/layout/PageHeader'
import flotteApi from '../../api/flotteApi'
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

function PivotTab() {
  const [groupBy, setGroupBy] = useState('vehicule')
  const [state, setState] = useState({ loading: true, error: null, data: null })

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
      <Segmented options={GROUP_BY_OPTIONS} value={groupBy} onChange={setGroupBy} aria-label="Regrouper par" />
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
      <Segmented
        options={years.map((y) => ({ value: String(y), label: String(y) }))}
        value={String(annee)}
        onChange={(v) => setAnnee(Number(v))}
        aria-label="Année"
      />
      <ListShell
        title={`Budget flotte ${annee} — vs réalisé`}
        columns={columns}
        rows={state.data?.categories || []}
        exportName={`budget-flotte-${annee}`}
        emptyTitle="Aucune catégorie"
        emptyDescription="Aucune ligne budgétaire."
      />
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
