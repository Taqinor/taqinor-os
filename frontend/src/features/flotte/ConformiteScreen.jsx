import { useCallback, useEffect, useMemo, useState } from 'react'
import { Tabs, TabsList, TabsTrigger, TabsContent, Label, Switch } from '../../ui'
import { EcheanceCenter, ListShell } from '../../ui/module'
import flotteApi from '../../api/flotteApi'
import { formatDate, formatMAD } from '../../lib/format'
import { ConformiteStatutPill } from './statusPills'
import { ECHEANCE_TYPES, alertesToEcheanceItems } from './flotte'
import useFlotteResource from './useFlotteResource'

/* ============================================================================
   UX19 — Conformité réglementaire (`/flotte/conformite`).
   ----------------------------------------------------------------------------
   Centre d'échéances AGRÉGÉ (FLOTTE24) : assurance, vignette/TSAV, visite
   technique, carte grise, entretiens datés — triés par urgence (échu → J-7 →
   J-15 → J-30) via l'`EcheanceCenter` (couleurs J-7/15/30/échu). Onglets par
   registre pour le détail éditable.
   ========================================================================== */

function AlertesCenter() {
  const [alertes, setAlertes] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const load = useCallback(() => {
    let cancelled = false
    setLoading(true)
    flotteApi.alertesEcheances()
      .then((res) => { if (!cancelled) { setAlertes(res?.data?.alertes ?? []); setError(null) } })
      .catch((err) => { if (!cancelled) setError(err?.response?.data?.detail || 'Alertes indisponibles.') })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { load() }, [load])
  const items = useMemo(() => alertesToEcheanceItems(alertes), [alertes])
  return (
    <EcheanceCenter
      title="Échéances réglementaires à surveiller"
      items={items}
      loading={loading}
      error={error}
      emptyText="Aucune échéance réglementaire dans les 30 prochains jours."
    />
  )
}

function EcheancesReglementairesTab() {
  const { data, loading, error } = useFlotteResource(flotteApi.echeancesReglementaires.list, {})
  const columns = useMemo(() => [
    { id: 'actif', header: 'Actif', width: 180, accessor: (r) => r.actif_label, cell: (v) => v || '—' },
    { id: 'type', header: 'Type', width: 160, accessor: (r) => r.type_echeance_display || ECHEANCE_TYPES[r.type_echeance] || r.type_echeance, cell: (v) => v || '—' },
    { id: 'date_echeance', header: 'Échéance', width: 130, accessor: (r) => r.date_echeance, cell: (v) => (v ? formatDate(v) : '—') },
    { id: 'organisme', header: 'Organisme', width: 160, accessor: (r) => r.organisme, cell: (v) => v || '—' },
    { id: 'statut', header: 'Statut', width: 130, accessor: (r) => r.statut_calcule || r.statut, cell: (v) => <ConformiteStatutPill status={v} /> },
  ], [])
  return (
    <ListShell
      title="Échéances réglementaires"
      columns={columns}
      rows={data}
      loading={loading}
      error={error}
      exportName="echeances-reglementaires"
      emptyTitle="Aucune échéance"
      emptyDescription="Aucune échéance réglementaire enregistrée."
    />
  )
}

function AssurancesTab() {
  const { data, loading, error } = useFlotteResource(flotteApi.assurances.list, {})
  const columns = useMemo(() => [
    { id: 'actif', header: 'Actif', width: 170, accessor: (r) => r.actif_label, cell: (v) => v || '—' },
    { id: 'assureur', header: 'Assureur', width: 160, accessor: (r) => r.assureur, cell: (v) => v || '—' },
    { id: 'numero_police', header: 'N° police', width: 150, accessor: (r) => r.numero_police, cell: (v) => v || '—' },
    { id: 'date_echeance', header: 'Échéance', width: 130, accessor: (r) => r.date_echeance, cell: (v) => (v ? formatDate(v) : '—') },
    { id: 'statut', header: 'Statut', width: 130, accessor: (r) => r.statut_calcule || r.statut, cell: (v) => <ConformiteStatutPill status={v} /> },
  ], [])
  return (
    <ListShell title="Assurances" columns={columns} rows={data} loading={loading} error={error}
      exportName="assurances" emptyTitle="Aucune assurance" emptyDescription="Aucune police enregistrée." />
  )
}

function VisitesTab() {
  const { data, loading, error } = useFlotteResource(flotteApi.visitesTechniques.list, {})
  const columns = useMemo(() => [
    { id: 'actif', header: 'Actif', width: 170, accessor: (r) => r.actif_label, cell: (v) => v || '—' },
    { id: 'centre', header: 'Centre', width: 160, accessor: (r) => r.centre, cell: (v) => v || '—' },
    { id: 'date_visite', header: 'Dernière visite', width: 140, accessor: (r) => r.date_visite, cell: (v) => (v ? formatDate(v) : '—') },
    { id: 'date_prochaine', header: 'Prochaine', width: 130, accessor: (r) => r.date_prochaine, cell: (v) => (v ? formatDate(v) : '—') },
    { id: 'resultat', header: 'Résultat', width: 130, accessor: (r) => r.resultat_display || r.resultat, cell: (v) => v || '—' },
    { id: 'statut', header: 'Statut', width: 130, accessor: (r) => r.statut_calcule || r.statut, cell: (v) => <ConformiteStatutPill status={v} /> },
  ], [])
  return (
    <ListShell title="Visites techniques" columns={columns} rows={data} loading={loading} error={error}
      exportName="visites-techniques" emptyTitle="Aucune visite" emptyDescription="Aucune visite technique enregistrée." />
  )
}

function CartesGrisesTab() {
  const { data, loading, error } = useFlotteResource(flotteApi.cartesGrises.list, {})
  const columns = useMemo(() => [
    { id: 'actif', header: 'Actif', width: 170, accessor: (r) => r.actif_label, cell: (v) => v || '—' },
    { id: 'numero', header: 'N° carte grise', width: 160, accessor: (r) => r.numero_carte_grise, cell: (v) => v || '—' },
    { id: 'immat', header: 'Immatriculée le', width: 150, accessor: (r) => r.date_immatriculation, cell: (v) => (v ? formatDate(v) : '—') },
    { id: 'autorisation', header: 'Autorisation valide', width: 160, accessor: (r) => r.autorisation_date_validite, cell: (v) => (v ? formatDate(v) : '—') },
    { id: 'statut', header: 'Statut', width: 130, accessor: (r) => r.statut_calcule || r.statut, cell: (v) => <ConformiteStatutPill status={v} /> },
  ], [])
  return (
    <ListShell title="Cartes grises & autorisations" columns={columns} rows={data} loading={loading} error={error}
      exportName="cartes-grises" emptyTitle="Aucune carte grise" emptyDescription="Aucune carte grise enregistrée." />
  )
}

function BaremesTab() {
  const { data, loading, error } = useFlotteResource(flotteApi.baremesVignette.list, {})
  const columns = useMemo(() => [
    { id: 'annee', header: 'Année', align: 'right', numeric: true, width: 100, accessor: (r) => r.annee, cell: (v) => v || '—' },
    { id: 'energie', header: 'Énergie', width: 130, accessor: (r) => r.energie_display || r.energie, cell: (v) => v || '—' },
    { id: 'cv', header: 'CV (min–max)', width: 140, searchable: false, accessor: (r) => `${r.cv_min ?? ''}-${r.cv_max ?? ''}`, cell: (_v, r) => `${r.cv_min ?? '—'} → ${r.cv_max ?? '—'}` },
    {
      id: 'montant',
      header: 'Montant TSAV',
      align: 'right',
      numeric: true,
      width: 140,
      searchable: false,
      accessor: (r) => Number(r.montant ?? 0),
      cell: (v) => (v ? `${v} MAD` : '—'),
    },
  ], [])
  return (
    <ListShell title="Barème vignette / TSAV" columns={columns} rows={data} loading={loading} error={error}
      exportName="baremes-vignette" emptyTitle="Aucun barème" emptyDescription="Aucun barème vignette défini." />
  )
}

// WIR236 — Contrats véhicule (XFLT1) : ni écran ni bascule « Expirants 30 j »
// (`GET /contrats-vehicule/expirants/?within=`, jamais appelé côté front).
function ContratsVehiculeTab() {
  const [expirants30j, setExpirants30j] = useState(false)
  const { data, loading, error } = useFlotteResource(
    (params) => (expirants30j
      ? flotteApi.contratsVehicule.expirants({ within: 30 })
      : flotteApi.contratsVehicule.list(params)),
    {},
    [expirants30j],
  )
  const columns = useMemo(() => [
    { id: 'vehicule', header: 'Véhicule', width: 160, accessor: (r) => r.vehicule_label, cell: (v) => v || '—' },
    { id: 'type_contrat', header: 'Type', width: 140, accessor: (r) => r.type_contrat_display || r.type_contrat, cell: (v) => v || '—' },
    { id: 'fournisseur', header: 'Bailleur/loueur', width: 160, accessor: (r) => r.fournisseur_label || r.fournisseur, cell: (v) => v || '—' },
    { id: 'date_debut', header: 'Début', width: 120, accessor: (r) => r.date_debut, cell: (v) => (v ? formatDate(v) : '—') },
    { id: 'date_fin', header: 'Fin', width: 120, accessor: (r) => r.date_fin, cell: (v) => (v ? formatDate(v) : '—') },
    {
      id: 'montant_recurrent', header: 'Montant récurrent', align: 'right', width: 150,
      accessor: (r) => Number(r.montant_recurrent ?? 0),
      cell: (v, r) => (v ? `${formatMAD(v)} / ${r.periodicite_display || r.periodicite}` : '—'),
    },
    { id: 'statut', header: 'Statut', width: 110, accessor: (r) => r.statut_calcule || r.statut, cell: (v) => v || '—' },
  ], [])

  const filters = (
    <div className="flex items-center gap-2">
      <Switch
        id="contrats-expirants-30j" checked={expirants30j}
        onCheckedChange={setExpirants30j}
      />
      <Label htmlFor="contrats-expirants-30j">Expirants ≤ 30 j</Label>
    </div>
  )

  return (
    <ListShell
      title="Contrats véhicule"
      subtitle="Leasing / LLD / location / entretien."
      filters={filters}
      columns={columns}
      rows={data}
      loading={loading}
      error={error}
      exportName="contrats-vehicule"
      emptyTitle="Aucun contrat"
      emptyDescription={expirants30j
        ? 'Aucun contrat expirant dans les 30 prochains jours.'
        : 'Aucun contrat véhicule enregistré.'}
    />
  )
}

export default function ConformiteScreen() {
  return (
    <div className="page flex flex-col gap-4">
      <h2 className="font-display text-xl font-semibold tracking-tight">Conformité réglementaire</h2>
      <AlertesCenter />
      <Tabs defaultValue="echeances">
        <TabsList className="flex-wrap">
          <TabsTrigger value="echeances">Échéances</TabsTrigger>
          <TabsTrigger value="assurances">Assurances</TabsTrigger>
          <TabsTrigger value="visites">Visites techniques</TabsTrigger>
          <TabsTrigger value="cartes">Cartes grises</TabsTrigger>
          <TabsTrigger value="contrats">Contrats véhicule</TabsTrigger>
          <TabsTrigger value="baremes">Barème TSAV</TabsTrigger>
        </TabsList>
        <TabsContent value="echeances"><EcheancesReglementairesTab /></TabsContent>
        <TabsContent value="assurances"><AssurancesTab /></TabsContent>
        <TabsContent value="visites"><VisitesTab /></TabsContent>
        <TabsContent value="cartes"><CartesGrisesTab /></TabsContent>
        <TabsContent value="contrats"><ContratsVehiculeTab /></TabsContent>
        <TabsContent value="baremes"><BaremesTab /></TabsContent>
      </Tabs>
    </div>
  )
}
