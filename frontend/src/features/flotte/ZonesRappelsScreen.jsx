import { useMemo } from 'react'
import { Tabs, TabsList, TabsTrigger, TabsContent, Badge, Button, toast } from '../../ui'
import { ListShell } from '../../ui/module'
import PageHeader from '../../components/layout/PageHeader'
import flotteApi from '../../api/flotteApi'
import { formatDate } from '../../lib/format'
import useFlotteResource from './useFlotteResource'

/* ============================================================================
   XFLT24/28 — Zones de géofencing & rappels constructeur (`/flotte/zones-rappels`).
   ----------------------------------------------------------------------------
   Zones : cercles de géofencing (dépôt/chantier/zone interdite) + bouton
   « Évaluer » (rapproche les relevés télématiques déjà ingérés, purement
   local). Rappels : campagnes constructeur + rapprochement idempotent contre
   le parc de VIN (crée un signalement XFLT5 par véhicule touché).
   ========================================================================== */

function ZonesTab() {
  const { data, loading, error } = useFlotteResource(flotteApi.zonesGeographiques.list, {})

  const evaluer = async () => {
    try {
      const res = await flotteApi.zonesGeographiques.evaluer()
      toast.success(`${res?.data?.nb_alertes ?? 0} alerte(s) détectée(s).`)
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Évaluation impossible.')
    }
  }

  const columns = useMemo(() => [
    { id: 'nom', header: 'Zone', width: 180, accessor: (r) => r.nom, cell: (v) => v || '—' },
    { id: 'type_zone', header: 'Type', width: 140, accessor: (r) => r.type_zone_display || r.type_zone, cell: (v) => v || '—' },
    { id: 'rayon_metres', header: 'Rayon', align: 'right', numeric: true, width: 100, searchable: false, accessor: (r) => r.rayon_metres, cell: (v) => (v != null ? `${v} m` : '—') },
    {
      id: 'plage',
      header: 'Plage autorisée',
      width: 150,
      searchable: false,
      accessor: (r) => `${r.heure_debut_autorisee || ''}-${r.heure_fin_autorisee || ''}`,
      cell: (_v, r) => (r.heure_debut_autorisee ? `${r.heure_debut_autorisee} → ${r.heure_fin_autorisee}` : 'Aucune restriction'),
    },
    {
      id: 'actif',
      header: 'Statut',
      width: 100,
      searchable: false,
      accessor: (r) => (r.actif ? 'Actif' : 'Inactif'),
      cell: (_v, r) => (r.actif ? <Badge tone="success">Actif</Badge> : <Badge tone="neutral">Inactif</Badge>),
    },
  ], [])

  const actions = (
    <Button variant="outline" onClick={evaluer}>Évaluer le géofencing</Button>
  )

  return (
    <ListShell
      title="Zones de géofencing"
      subtitle="Dépôt, chantier, zone interdite — plage horaire autorisée optionnelle."
      actions={actions}
      columns={columns}
      rows={data}
      loading={loading}
      error={error}
      exportName="zones-geographiques"
      emptyTitle="Aucune zone"
      emptyDescription="Aucune zone de géofencing définie."
    />
  )
}

function RappelsTab() {
  const { data, loading, error, reload } = useFlotteResource(flotteApi.rappelsConstructeur.list, {})

  const rapprocher = async (row) => {
    try {
      const res = await flotteApi.rappelsConstructeur.rapprocher(row.id)
      toast.success(`${res?.data?.nb_vin_matches ?? 0} véhicule(s) touché(s).`)
      reload()
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Rapprochement impossible.')
    }
  }

  const columns = useMemo(() => [
    { id: 'reference_campagne', header: 'Référence', width: 160, accessor: (r) => r.reference_campagne, cell: (v) => v || '—' },
    { id: 'constructeur', header: 'Constructeur', width: 150, accessor: (r) => r.constructeur, cell: (v) => v || '—' },
    { id: 'description', header: 'Description', width: 260, accessor: (r) => r.description, cell: (v) => v || '—' },
    {
      id: 'vin_concernes',
      header: 'VIN concernés',
      align: 'right',
      numeric: true,
      width: 130,
      searchable: false,
      accessor: (r) => (Array.isArray(r.vin_concernes) ? r.vin_concernes.length : 0),
      cell: (v) => v,
    },
    { id: 'date_creation', header: 'Créé le', width: 130, accessor: (r) => r.date_creation, cell: (v) => (v ? formatDate(v) : '—') },
  ], [])

  const rowActions = (row) => [
    { id: 'rapprocher', label: 'Rapprocher contre le parc', onClick: () => rapprocher(row) },
  ]

  return (
    <ListShell
      title="Rappels constructeur"
      subtitle="Rapprochement idempotent contre le parc de VIN — crée un signalement par véhicule touché."
      columns={columns}
      rows={data}
      loading={loading}
      error={error}
      rowActions={rowActions}
      exportName="rappels-constructeur"
      emptyTitle="Aucun rappel"
      emptyDescription="Aucune campagne de rappel enregistrée."
    />
  )
}

export default function ZonesRappelsScreen() {
  return (
    <div className="page flex flex-col gap-4">
      <PageHeader
        title="Zones & rappels constructeur"
        subtitle="Géofencing du parc et campagnes de rappel constructeur."
      />
      <Tabs defaultValue="zones">
        <TabsList className="flex-wrap">
          <TabsTrigger value="zones">Zones de géofencing</TabsTrigger>
          <TabsTrigger value="rappels">Rappels constructeur</TabsTrigger>
        </TabsList>
        <TabsContent value="zones"><ZonesTab /></TabsContent>
        <TabsContent value="rappels"><RappelsTab /></TabsContent>
      </Tabs>
    </div>
  )
}
