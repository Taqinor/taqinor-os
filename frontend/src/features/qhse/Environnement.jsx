import { useEffect, useMemo, useState } from 'react'
import { Leaf } from 'lucide-react'
import qhseApi from '../../api/qhseApi'
import { Tabs, TabsList, TabsTrigger, TabsContent, Badge, Card } from '../../ui'
import { BarArrondie } from '../../ui/charts'
import { formatDate, formatNumber } from '../../lib/format'
import { QhseResourceList } from './QhseResourceList'
import { rowsFrom } from './useQhseList'
import {
  BsdStatutPill, RecyclageStatutPill, ConformiteStatutPill, BilanStatutPill,
  EsgPilierPill,
} from './qhsePills'
import { num } from './qhseStatus'

/* ============================================================================
   UX33 — Environnement & ESG.
   ----------------------------------------------------------------------------
   Onglets :
   • Déchets : référentiel déchets + bordereaux de suivi (BSD, loi 28-00).
   • Recyclage PV : recyclage des modules photovoltaïques.
   • Conformité : conformités environnementales (autorisations, échéances).
   • Bilan carbone : bilans (scopes 1/2/3) avec graphe tCO₂e + lignes.
   • ESG : indicateurs E/S/G.
   ========================================================================== */

function BilanCarboneChart() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let alive = true
    qhseApi.bilansCarbone.list()
      .then((res) => { if (alive) setRows(rowsFrom(res)) })
      .catch(() => { if (alive) setRows([]) })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [])

  // Bilan le plus récent (année max) → décomposition par scope.
  const latest = useMemo(() => {
    if (!rows.length) return null
    return [...rows].sort((a, b) => (b.annee ?? 0) - (a.annee ?? 0))[0]
  }, [rows])

  if (loading || !latest) return null

  const scopes = [
    { label: 'Scope 1', value: num(latest.total_scope_1) ?? 0 },
    { label: 'Scope 2', value: num(latest.total_scope_2) ?? 0 },
    { label: 'Scope 3', value: num(latest.total_scope_3) ?? 0 },
  ]
  const total = num(latest.total_tco2e) ?? 0

  return (
    <Card className="p-4 sm:p-5">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h3 className="font-display text-base font-semibold tracking-tight">
          Bilan carbone {latest.annee ?? ''} — {latest.libelle}
        </h3>
        <Badge tone="success">
          {formatNumber(total, { decimals: 2 })} tCO₂e
        </Badge>
      </div>
      <BarArrondie
        data={scopes}
        height={200}
        tone="success"
        name="tCO₂e"
        tooltipFormat={(v) => `${formatNumber(v, { decimals: 2 })} tCO₂e`}
      />
    </Card>
  )
}

export default function Environnement() {
  const [tab, setTab] = useState('dechets')

  const dechetsCols = useMemo(() => [
    { id: 'libelle', header: 'Déchet', accessor: (r) => r.libelle },
    { id: 'code', header: 'Code', width: 120, accessor: (r) => r.code || '—' },
    { id: 'categorie', header: 'Catégorie', width: 150, accessor: (r) => r.categorie_display || r.categorie },
    {
      id: 'dangereux', header: 'Dangereux', width: 110, align: 'center',
      accessor: (r) => r.dangereux,
      cell: (v) => <Badge tone={v ? 'danger' : 'neutral'}>{v ? 'Oui' : 'Non'}</Badge>,
    },
    { id: 'mode', header: 'Traitement', width: 160, accessor: (r) => r.mode_traitement_display || r.mode_traitement },
  ], [])

  const bsdCols = useMemo(() => [
    { id: 'reference', header: 'Réf.', width: 130, accessor: (r) => r.reference },
    { id: 'dechet', header: 'Déchet', accessor: (r) => r.dechet_libelle || r.dechet },
    {
      id: 'quantite', header: 'Quantité', width: 120, align: 'right',
      accessor: (r) => r.quantite,
      cell: (v) => (v == null ? '—' : formatNumber(v, { decimals: 2 })),
    },
    { id: 'eliminateur', header: 'Éliminateur', accessor: (r) => r.eliminateur || '—' },
    {
      id: 'statut', header: 'Statut', width: 120,
      accessor: (r) => r.statut, cell: (v) => <BsdStatutPill status={v} />,
    },
  ], [])

  const recyclageCols = useMemo(() => [
    { id: 'reference', header: 'Réf.', width: 130, accessor: (r) => r.reference },
    { id: 'marque', header: 'Marque / modèle', accessor: (r) => [r.marque, r.modele].filter(Boolean).join(' ') || '—' },
    { id: 'nombre', header: 'Modules', width: 100, align: 'right', accessor: (r) => r.nombre_modules ?? 0 },
    { id: 'motif', header: 'Motif', width: 140, accessor: (r) => r.motif_display || r.motif },
    {
      id: 'statut', header: 'Statut', width: 130,
      accessor: (r) => r.statut, cell: (v) => <RecyclageStatutPill status={v} />,
    },
  ], [])

  const conformiteCols = useMemo(() => [
    { id: 'intitule', header: 'Conformité', accessor: (r) => r.intitule },
    { id: 'type', header: 'Type', width: 170, accessor: (r) => r.type_conformite_display || r.type_conformite },
    { id: 'autorite', header: 'Autorité', accessor: (r) => r.autorite || '—' },
    {
      id: 'date_expiration', header: 'Expiration', width: 130, align: 'right',
      accessor: (r) => r.date_expiration, cell: (v) => formatDate(v),
    },
    {
      id: 'statut', header: 'Statut', width: 140,
      accessor: (r) => r.statut, cell: (v) => <ConformiteStatutPill status={v} />,
    },
  ], [])

  const bilanCols = useMemo(() => [
    { id: 'libelle', header: 'Bilan', accessor: (r) => r.libelle },
    { id: 'annee', header: 'Année', width: 90, align: 'right', accessor: (r) => r.annee ?? '—' },
    {
      id: 'total', header: 'Total tCO₂e', width: 140, align: 'right',
      accessor: (r) => num(r.total_tco2e) ?? 0,
      cell: (v) => formatNumber(v, { decimals: 2 }),
    },
    {
      id: 'statut', header: 'Statut', width: 120,
      accessor: (r) => r.statut, cell: (v) => <BilanStatutPill status={v} />,
    },
  ], [])

  const esgCols = useMemo(() => [
    { id: 'code', header: 'Code', width: 110, accessor: (r) => r.code },
    { id: 'libelle', header: 'Indicateur', accessor: (r) => r.libelle },
    {
      id: 'pilier', header: 'Pilier', width: 150,
      accessor: (r) => r.pilier, cell: (v) => <EsgPilierPill status={v} />,
    },
    {
      id: 'valeur', header: 'Valeur', width: 120, align: 'right',
      accessor: (r) => r.valeur,
      cell: (v, r) => `${formatNumber(v, {})}${r.unite ? ` ${r.unite}` : ''}`,
    },
    {
      id: 'atteinte_cible', header: 'Cible atteinte', width: 140, align: 'center',
      accessor: (r) => r.atteinte_cible,
      cell: (v) =>
        v == null
          ? <span className="text-muted-foreground">—</span>
          : <Badge tone={v ? 'success' : 'warning'}>{v ? 'Oui' : 'Non'}</Badge>,
    },
  ], [])

  return (
    <div className="page flex flex-col gap-4">
      <div className="page-header">
        <h2 className="flex items-center gap-2">
          <Leaf size={20} strokeWidth={1.75} aria-hidden="true" />
          Environnement & ESG
        </h2>
      </div>

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList className="flex-wrap">
          <TabsTrigger value="dechets">Déchets</TabsTrigger>
          <TabsTrigger value="recyclage">Recyclage PV</TabsTrigger>
          <TabsTrigger value="conformite">Conformité</TabsTrigger>
          <TabsTrigger value="carbone">Bilan carbone</TabsTrigger>
          <TabsTrigger value="esg">ESG</TabsTrigger>
        </TabsList>

        <TabsContent value="dechets" className="mt-4 flex flex-col gap-6">
          <QhseResourceList
            title="Référentiel des déchets"
            subtitle="Loi 28-00 — catégories & modes de traitement"
            fetcher={() => qhseApi.dechets.list()}
            columns={dechetsCols}
            exportName="qhse-dechets"
          />
          <QhseResourceList
            title="Bordereaux de suivi (BSD)"
            subtitle="Déchets dangereux — producteur → transporteur → éliminateur"
            fetcher={() => qhseApi.bordereauxDechets.list()}
            columns={bsdCols}
            exportName="qhse-bsd"
          />
        </TabsContent>

        <TabsContent value="recyclage" className="mt-4">
          <QhseResourceList
            title="Recyclage des modules PV"
            subtitle="Collecte → transport → recyclage (filière)"
            fetcher={() => qhseApi.recyclageModules.list()}
            columns={recyclageCols}
            exportName="qhse-recyclage-modules"
          />
        </TabsContent>

        <TabsContent value="conformite" className="mt-4">
          <QhseResourceList
            title="Conformités environnementales"
            subtitle="Autorisations, études d’impact, rejets — échéances"
            fetcher={() => qhseApi.conformitesEnvironnementales.list()}
            columns={conformiteCols}
            exportName="qhse-conformites-env"
          />
        </TabsContent>

        <TabsContent value="carbone" className="mt-4 flex flex-col gap-6">
          <BilanCarboneChart />
          <QhseResourceList
            title="Bilans carbone"
            subtitle="Scopes 1/2/3 (tCO₂e)"
            fetcher={() => qhseApi.bilansCarbone.list()}
            columns={bilanCols}
            exportName="qhse-bilans-carbone"
          />
        </TabsContent>

        <TabsContent value="esg" className="mt-4">
          <QhseResourceList
            title="Indicateurs ESG"
            subtitle="Environnement · Social · Gouvernance"
            fetcher={() => qhseApi.indicateursEsg.list()}
            columns={esgCols}
            exportName="qhse-indicateurs-esg"
          />
        </TabsContent>
      </Tabs>
    </div>
  )
}
