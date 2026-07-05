import { useMemo } from 'react'
import { Tabs, TabsList, TabsTrigger, TabsContent, Badge } from '../../ui'
import { ListShell, EcheanceCenter } from '../../ui/module'
import flotteApi from '../../api/flotteApi'
import { formatDate, formatNumber } from '../../lib/format'
import { EntretienStatutPill, OrStatutPill } from './statusPills'
import { PNEU_POSITIONS, PNEU_STATUTS } from './flotte'
import useFlotteResource from './useFlotteResource'

/* ============================================================================
   UX18 — Entretien (`/flotte/entretien`).
   ----------------------------------------------------------------------------
   Onglets : plans préventifs, échéances d'entretien (timeline via
   `EcheanceCenter`), garages, ordres de réparation (main-d'œuvre + pièces),
   pneumatiques, pièces. Les coûts affichés sont des coûts d'EXPLOITATION
   internes (jamais des prix client ni des prix d'achat/marge).
   ========================================================================== */

function PlansTab() {
  const { data, loading, error } = useFlotteResource(flotteApi.plansEntretien.list, {})
  const columns = useMemo(() => [
    { id: 'actif', header: 'Actif', width: 200, accessor: (r) => r.actif_label, cell: (v) => v || '—' },
    { id: 'type_entretien', header: 'Type', width: 180, accessor: (r) => r.type_entretien, cell: (v) => v || '—' },
    { id: 'intervalle_km', header: 'Interv. km', align: 'right', numeric: true, width: 120, accessor: (r) => r.intervalle_km, cell: (v) => (v ? `${formatNumber(v)} km` : '—') },
    { id: 'intervalle_jours', header: 'Interv. jours', align: 'right', numeric: true, width: 130, accessor: (r) => r.intervalle_jours, cell: (v) => (v ? `${v} j` : '—') },
    {
      id: 'actif_bool',
      header: 'Plan',
      width: 100,
      searchable: false,
      accessor: (r) => (r.actif ? 'Actif' : 'Inactif'),
      cell: (_v, r) => (r.actif ? <Badge tone="success">Actif</Badge> : <Badge tone="neutral">Inactif</Badge>),
    },
  ], [])
  return (
    <ListShell
      title="Plans d’entretien préventif"
      columns={columns}
      rows={data}
      loading={loading}
      error={error}
      exportName="plans-entretien"
      emptyTitle="Aucun plan"
      emptyDescription="Aucun plan d’entretien défini."
    />
  )
}

function EcheancesTab() {
  const { data, loading, error } = useFlotteResource(flotteApi.echeancesEntretien.list, { ouvertes: 'true' })
  const items = useMemo(
    () => (data || []).map((e) => ({
      id: `ent-${e.id}`,
      label: `${e.type_entretien || 'Entretien'} — ${e.actif_label || ''}`.trim(),
      date: e.due_le,
      meta: e.statut_display || e.statut,
    })),
    [data],
  )
  const columns = useMemo(() => [
    { id: 'actif', header: 'Actif', width: 200, accessor: (r) => r.actif_label, cell: (v) => v || '—' },
    { id: 'type_entretien', header: 'Type', width: 180, accessor: (r) => r.type_entretien, cell: (v) => v || '—' },
    { id: 'due_le', header: 'Échéance', width: 130, accessor: (r) => r.due_le, cell: (v) => (v ? formatDate(v) : '—') },
    { id: 'due_km', header: 'Échéance km', align: 'right', numeric: true, width: 130, accessor: (r) => r.due_km, cell: (v) => (v ? `${formatNumber(v)} km` : '—') },
    { id: 'statut', header: 'Statut', width: 120, accessor: (r) => r.statut, cell: (v) => <EntretienStatutPill status={v} /> },
  ], [])
  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_340px]">
      <ListShell
        title="Échéances d’entretien"
        columns={columns}
        rows={data}
        loading={loading}
        error={error}
        exportName="echeances-entretien"
        emptyTitle="Aucune échéance ouverte"
        emptyDescription="Aucune échéance d’entretien à traiter."
      />
      <EcheanceCenter title="Prochains entretiens" items={items} loading={loading} max={12} />
    </div>
  )
}

function GaragesTab() {
  const { data, loading, error } = useFlotteResource(flotteApi.garages.list, {})
  const columns = useMemo(() => [
    { id: 'nom', header: 'Garage', width: 200, accessor: (r) => r.nom, cell: (v) => v || '—' },
    { id: 'adresse', header: 'Adresse', width: 240, accessor: (r) => r.adresse, cell: (v) => v || '—' },
    { id: 'telephone', header: 'Téléphone', width: 150, accessor: (r) => r.telephone, cell: (v) => v || '—' },
    {
      id: 'actif',
      header: 'Statut',
      width: 100,
      searchable: false,
      accessor: (r) => (r.actif ? 'Actif' : 'Inactif'),
      cell: (_v, r) => (r.actif ? <Badge tone="success">Actif</Badge> : <Badge tone="neutral">Inactif</Badge>),
    },
  ], [])
  return (
    <ListShell
      title="Garages"
      columns={columns}
      rows={data}
      loading={loading}
      error={error}
      exportName="garages"
      emptyTitle="Aucun garage"
      emptyDescription="Aucun garage référencé."
    />
  )
}

function OrdresTab() {
  const { data, loading, error } = useFlotteResource(flotteApi.ordresReparation.list, {})
  const columns = useMemo(() => [
    { id: 'actif', header: 'Actif', width: 180, accessor: (r) => r.actif_label, cell: (v) => v || '—' },
    { id: 'garage', header: 'Garage', width: 160, accessor: (r) => r.garage_nom, cell: (v) => v || '—' },
    // ZCTR10 — type de service/entretien (référentiel éditable) ; absence = "non catégorisé".
    { id: 'type_service', header: 'Type de service', width: 160, accessor: (r) => r.type_service_libelle, cell: (v) => v || 'Non catégorisé' },
    { id: 'description', header: 'Description', width: 220, accessor: (r) => r.description, cell: (v) => v || '—' },
    { id: 'date_ouverture', header: 'Ouvert le', width: 130, accessor: (r) => r.date_ouverture, cell: (v) => (v ? formatDate(v) : '—') },
    {
      id: 'cout_total',
      header: 'Coût total',
      align: 'right',
      numeric: true,
      width: 130,
      searchable: false,
      accessor: (r) => Number(r.cout_total ?? 0),
      cell: (v) => (v ? `${formatNumber(v, { decimals: 2 })} MAD` : '—'),
    },
    { id: 'statut', header: 'Statut', width: 120, accessor: (r) => r.statut, cell: (v) => <OrStatutPill status={v} /> },
  ], [])
  return (
    <ListShell
      title="Ordres de réparation"
      subtitle="Main-d’œuvre + pièces (coûts d’exploitation internes)."
      columns={columns}
      rows={data}
      loading={loading}
      error={error}
      exportName="ordres-reparation"
      emptyTitle="Aucun ordre"
      emptyDescription="Aucun ordre de réparation ouvert."
    />
  )
}

function PneusTab() {
  const { data, loading, error } = useFlotteResource(flotteApi.pneumatiques.list, {})
  const columns = useMemo(() => [
    { id: 'vehicule', header: 'Véhicule', width: 170, accessor: (r) => r.vehicule_label, cell: (v) => v || '—' },
    { id: 'position', header: 'Position', width: 130, accessor: (r) => r.position_display || PNEU_POSITIONS[r.position] || r.position, cell: (v) => v || '—' },
    { id: 'marque', header: 'Marque', width: 140, accessor: (r) => r.marque, cell: (v) => v || '—' },
    { id: 'dimension', header: 'Dimension', width: 130, accessor: (r) => r.dimension, cell: (v) => v || '—' },
    { id: 'date_montage', header: 'Montage', width: 120, accessor: (r) => r.date_montage, cell: (v) => (v ? formatDate(v) : '—') },
    { id: 'statut', header: 'Statut', width: 110, accessor: (r) => r.statut_display || PNEU_STATUTS[r.statut] || r.statut, cell: (v) => v || '—' },
  ], [])
  return (
    <ListShell
      title="Pneumatiques"
      columns={columns}
      rows={data}
      loading={loading}
      error={error}
      exportName="pneumatiques"
      emptyTitle="Aucun pneu"
      emptyDescription="Aucun pneumatique enregistré."
    />
  )
}

function PiecesTab() {
  const { data, loading, error } = useFlotteResource(flotteApi.pieces.list, {})
  const columns = useMemo(() => [
    { id: 'vehicule', header: 'Véhicule', width: 170, accessor: (r) => r.vehicule_label, cell: (v) => v || '—' },
    { id: 'designation', header: 'Désignation', width: 220, accessor: (r) => r.designation, cell: (v) => v || '—' },
    { id: 'reference', header: 'Référence', width: 140, accessor: (r) => r.reference, cell: (v) => v || '—' },
    { id: 'quantite', header: 'Qté', align: 'right', numeric: true, width: 80, accessor: (r) => r.quantite, cell: (v) => (v != null ? v : '—') },
    {
      id: 'cout_total',
      header: 'Coût',
      align: 'right',
      numeric: true,
      width: 130,
      searchable: false,
      accessor: (r) => Number(r.cout_total ?? 0),
      cell: (v) => (v ? `${formatNumber(v, { decimals: 2 })} MAD` : '—'),
    },
    { id: 'date_pose', header: 'Posée le', width: 120, accessor: (r) => r.date_pose, cell: (v) => (v ? formatDate(v) : '—') },
  ], [])
  return (
    <ListShell
      title="Pièces"
      subtitle="Pièces consommées (coûts d’exploitation internes)."
      columns={columns}
      rows={data}
      loading={loading}
      error={error}
      exportName="pieces"
      emptyTitle="Aucune pièce"
      emptyDescription="Aucune pièce enregistrée."
    />
  )
}

export default function EntretienScreen() {
  return (
    <div className="page flex flex-col gap-4">
      <h2 className="font-display text-xl font-semibold tracking-tight">Entretien & réparations</h2>
      <Tabs defaultValue="echeances">
        <TabsList className="flex-wrap">
          <TabsTrigger value="echeances">Échéances</TabsTrigger>
          <TabsTrigger value="plans">Plans</TabsTrigger>
          <TabsTrigger value="ordres">Ordres de réparation</TabsTrigger>
          <TabsTrigger value="garages">Garages</TabsTrigger>
          <TabsTrigger value="pneus">Pneumatiques</TabsTrigger>
          <TabsTrigger value="pieces">Pièces</TabsTrigger>
        </TabsList>
        <TabsContent value="echeances"><EcheancesTab /></TabsContent>
        <TabsContent value="plans"><PlansTab /></TabsContent>
        <TabsContent value="ordres"><OrdresTab /></TabsContent>
        <TabsContent value="garages"><GaragesTab /></TabsContent>
        <TabsContent value="pneus"><PneusTab /></TabsContent>
        <TabsContent value="pieces"><PiecesTab /></TabsContent>
      </Tabs>
    </div>
  )
}
