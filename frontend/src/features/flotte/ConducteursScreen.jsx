import { useCallback, useMemo, useState } from 'react'
import { UserPlus, AlertTriangle, FileCheck } from 'lucide-react'
import {
  Button, Badge, Segmented, Tabs, TabsList, TabsTrigger, TabsContent,
  toast,
} from '../../ui'
import { ListShell } from '../../ui/module'
import flotteApi from '../../api/flotteApi'
import { formatDate, formatDateTime, formatPhoneMA } from '../../lib/format'
import { daysUntil, urgencyTone } from '../../ui/module'
import useFlotteResource from './useFlotteResource'
import AffectationDialog from './AffectationDialog'
import MasseAffectationDialog from './MasseAffectationDialog'
import SignatureDialog from './SignatureDialog'
import ConducteurDialog from './ConducteurDialog'

/* ============================================================================
   UX17 — Conducteurs & affectations (`/flotte/conducteurs`).
   ----------------------------------------------------------------------------
   Onglets : conducteurs (avec validité de permis), affectations conducteur↔
   véhicule (création BLOQUÉE si le permis est invalide — message FR clair,
   FLOTTE9), réservations / demandes de pool, états des lieux. Le contrôle de
   permis est répliqué côté client (`controlePermis`) pour un retour immédiat,
   et re-vérifié côté serveur à l'enregistrement.
   ========================================================================== */

const ACTIF_FILTERS = [
  { value: '', label: 'Tous' },
  { value: 'true', label: 'Actifs' },
  { value: 'false', label: 'Inactifs' },
]

// Badge de validité du permis à partir de la date d'expiration.
function PermisBadge({ dateExpiration }) {
  if (!dateExpiration) return <Badge tone="neutral">Non renseigné</Badge>
  const d = daysUntil(dateExpiration)
  if (d == null) return <Badge tone="neutral">—</Badge>
  if (d < 0) return <Badge tone="danger">Expiré</Badge>
  const tone = urgencyTone(d < 0 ? 'overdue' : d <= 30 ? 'soon' : 'ok')
  return <Badge tone={tone}>{d <= 30 ? `Expire J-${d}` : 'Valide'}</Badge>
}

function ConducteursTab() {
  const [actif, setActif] = useState('')
  const [showForm, setShowForm] = useState(false)
  const params = useMemo(() => (actif ? { actif } : {}), [actif])
  const { data, loading, error, reload } = useFlotteResource(flotteApi.conducteurs.list, params)

  const columns = useMemo(() => [
    { id: 'nom', header: 'Conducteur', width: 200, accessor: (r) => r.nom, cell: (v) => v || '—' },
    {
      id: 'telephone',
      header: 'Téléphone',
      width: 150,
      accessor: (r) => r.telephone,
      cell: (v) => (v ? formatPhoneMA(v) : '—'),
    },
    {
      id: 'numero_permis',
      header: 'N° permis',
      width: 140,
      accessor: (r) => r.numero_permis,
      cell: (v) => (v ? <span className="font-mono text-xs">{v}</span> : '—'),
    },
    {
      id: 'categorie_permis',
      header: 'Catégories',
      width: 120,
      accessor: (r) => r.categorie_permis,
      cell: (v) => v || '—',
    },
    {
      id: 'date_expiration',
      header: 'Expiration',
      width: 130,
      accessor: (r) => r.date_expiration,
      cell: (v) => (v ? formatDate(v) : '—'),
    },
    {
      id: 'validite',
      header: 'Validité',
      width: 130,
      searchable: false,
      accessor: (r) => r.date_expiration,
      cell: (v) => <PermisBadge dateExpiration={v} />,
    },
  ], [])

  const filters = (
    <Segmented options={ACTIF_FILTERS} value={actif} onChange={setActif} aria-label="Filtrer par activité" />
  )

  const actions = (
    <Button onClick={() => setShowForm(true)}>
      <UserPlus /> Nouveau conducteur
    </Button>
  )

  return (
    <>
      <ListShell
        title="Conducteurs"
        subtitle="Chauffeurs et validité de leur permis."
        filters={filters}
        actions={actions}
        columns={columns}
        rows={data}
        loading={loading}
        error={error}
        searchable
        searchPlaceholder="Rechercher nom, permis, téléphone…"
        exportName="conducteurs"
        emptyTitle="Aucun conducteur"
        emptyDescription="Aucun conducteur ne correspond à ces filtres."
      />
      {showForm && (
        <ConducteurDialog
          onClose={() => setShowForm(false)}
          onSaved={() => { setShowForm(false); reload(); toast.success('Conducteur créé.') }}
        />
      )}
    </>
  )
}

function AffectationsTab({ conducteurs, vehicules }) {
  const [showForm, setShowForm] = useState(false)
  const [showMasse, setShowMasse] = useState(false)
  const { data, loading, error, reload } = useFlotteResource(flotteApi.affectations.list, {})

  const columns = useMemo(() => [
    { id: 'conducteur', header: 'Conducteur', width: 180, accessor: (r) => r.conducteur_nom || r.conducteur, cell: (v) => v || '—' },
    { id: 'vehicule', header: 'Véhicule', width: 180, accessor: (r) => r.vehicule_label || r.vehicule, cell: (v) => v || '—' },
    { id: 'date_debut', header: 'Début', width: 120, accessor: (r) => r.date_debut, cell: (v) => (v ? formatDate(v) : '—') },
    { id: 'date_fin', header: 'Fin', width: 120, accessor: (r) => r.date_fin, cell: (v) => (v ? formatDate(v) : '—') },
    {
      id: 'actif',
      header: 'Statut',
      width: 110,
      searchable: false,
      accessor: (r) => (r.actif ? 'Active' : 'Terminée'),
      cell: (_v, r) => (r.actif ? <Badge tone="success">Active</Badge> : <Badge tone="neutral">Terminée</Badge>),
    },
    {
      id: 'avertissement',
      header: 'Alerte permis',
      width: 200,
      searchable: false,
      accessor: (r) => r.permis_avertissement || '',
      cell: (v) => (v
        ? (
          <span className="inline-flex items-center gap-1 text-xs text-warning">
            <AlertTriangle className="size-3.5" aria-hidden="true" /> {v}
          </span>
        )
        : <span className="text-muted-foreground">—</span>),
    },
  ], [])

  const actions = (
    <div className="flex items-center gap-2">
      <Button variant="outline" onClick={() => setShowMasse(true)}>Réaffectation en masse</Button>
      <Button onClick={() => setShowForm(true)}>
        <UserPlus /> Nouvelle affectation
      </Button>
    </div>
  )

  return (
    <>
      <ListShell
        title="Affectations"
        subtitle="Attribution datée d’un véhicule à un conducteur."
        actions={actions}
        columns={columns}
        rows={data}
        loading={loading}
        error={error}
        exportName="affectations"
        emptyTitle="Aucune affectation"
        emptyDescription="Créez une affectation pour attribuer un véhicule."
      />
      {showForm && (
        <AffectationDialog
          conducteurs={conducteurs}
          vehicules={vehicules}
          onClose={() => setShowForm(false)}
          onSaved={() => { setShowForm(false); reload(); toast.success('Affectation enregistrée.') }}
        />
      )}
      {showMasse && (
        <MasseAffectationDialog
          conducteurs={conducteurs}
          vehicules={vehicules}
          onClose={() => setShowMasse(false)}
          onSaved={() => { setShowMasse(false); reload(); toast.success('Réaffectation en masse enregistrée.') }}
        />
      )}
    </>
  )
}

function ReservationsTab() {
  const { data, loading, error } = useFlotteResource(flotteApi.reservations.list, {})
  const columns = useMemo(() => [
    { id: 'vehicule', header: 'Véhicule', width: 180, accessor: (r) => r.vehicule_label || r.vehicule, cell: (v) => v || '—' },
    { id: 'conducteur', header: 'Conducteur', width: 160, accessor: (r) => r.conducteur_nom || r.conducteur, cell: (v) => v || '—' },
    { id: 'debut', header: 'Début', width: 150, accessor: (r) => r.debut, cell: (v) => (v ? formatDate(v) : '—') },
    { id: 'fin', header: 'Fin', width: 150, accessor: (r) => r.fin, cell: (v) => (v ? formatDate(v) : '—') },
    { id: 'motif', header: 'Motif', width: 200, accessor: (r) => r.motif, cell: (v) => v || '—' },
    { id: 'statut', header: 'Statut', width: 120, accessor: (r) => r.statut_display || r.statut, cell: (v) => v || '—' },
  ], [])
  return (
    <ListShell
      title="Réservations & demandes de pool"
      subtitle="Créneaux réservés et demandes de véhicule en attente."
      columns={columns}
      rows={data}
      loading={loading}
      error={error}
      exportName="reservations"
      emptyTitle="Aucune réservation"
      emptyDescription="Aucune réservation enregistrée."
    />
  )
}

function EtatsDesLieuxTab() {
  const { data, loading, error, reload } = useFlotteResource(flotteApi.etatsDesLieux.list, {})
  const [signing, setSigning] = useState(null) // { etat, role }

  const columns = useMemo(() => [
    { id: 'vehicule', header: 'Véhicule', width: 170, accessor: (r) => r.vehicule_label || r.vehicule, cell: (v) => v || '—' },
    { id: 'moment', header: 'Moment', width: 100, accessor: (r) => r.moment_display || r.moment, cell: (v) => v || '—' },
    { id: 'date_constat', header: 'Date', width: 120, accessor: (r) => r.date_constat, cell: (v) => (v ? formatDate(v) : '—') },
    { id: 'kilometrage', header: 'Km', align: 'right', numeric: true, width: 100, accessor: (r) => r.kilometrage, cell: (v) => (v != null ? v : '—') },
    { id: 'etat_general', header: 'État', width: 100, accessor: (r) => r.etat_general_display || r.etat_general, cell: (v) => v || '—' },
    { id: 'nb_photos', header: 'Photos', align: 'right', numeric: true, width: 80, searchable: false, accessor: (r) => r.nb_photos ?? 0, cell: (v) => v ?? 0 },
    {
      // XFLT17 — état des signatures (loi 53-05, nom saisi + horodatage serveur).
      id: 'signatures',
      header: 'Signatures',
      width: 180,
      searchable: false,
      accessor: (r) => `${r.signature_conducteur || ''}|${r.signature_responsable || ''}`,
      cell: (_v, r) => (
        <div className="flex flex-col gap-0.5 text-xs">
          <span className={r.signature_conducteur ? 'text-success' : 'text-muted-foreground'}>
            Conducteur : {r.signature_conducteur || 'non signé'}
          </span>
          <span className={r.signature_responsable ? 'text-success' : 'text-muted-foreground'}>
            Responsable : {r.signature_responsable || 'non signé'}
          </span>
        </div>
      ),
    },
  ], [])

  const rowActions = (row) => {
    const actions = []
    if (!row.signature_conducteur) {
      actions.push({ id: 'sign-cond', label: 'Signer (conducteur)', onClick: () => setSigning({ etat: row, role: 'conducteur' }) })
    }
    if (!row.signature_responsable) {
      actions.push({ id: 'sign-resp', label: 'Signer (responsable)', onClick: () => setSigning({ etat: row, role: 'responsable' }) })
    }
    return actions
  }

  return (
    <>
      <ListShell
        title="États des lieux"
        subtitle="Constats départ / retour avec relevé kilométrique et e-signature."
        columns={columns}
        rows={data}
        loading={loading}
        error={error}
        rowActions={rowActions}
        exportName="etats-des-lieux"
        emptyTitle="Aucun état des lieux"
        emptyDescription="Aucun constat enregistré."
      />
      {signing && (
        <SignatureDialog
          etat={signing.etat}
          role={signing.role}
          onClose={() => setSigning(null)}
          onSaved={() => { setSigning(null); reload(); toast.success('Signature enregistrée.') }}
        />
      )}
    </>
  )
}

function CharteTab({ conducteurs }) {
  const { data: charte, loading: loadingCharte } = useFlotteResource(flotteApi.chartesVehicule.list, {})
  const { data: accuses, loading: loadingAccuses, reload } = useFlotteResource(flotteApi.accusesCharte.list, {})
  const derniere = useMemo(
    () => [...(charte || [])].sort((a, b) => (b.version || 0) - (a.version || 0))[0] || null,
    [charte],
  )

  const accuser = useCallback(async (conducteurId) => {
    try {
      await flotteApi.accusesCharte.create({ conducteur: conducteurId })
      toast.success('Accusé de lecture enregistré.')
      reload()
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Enregistrement impossible.')
    }
  }, [reload])

  const columns = useMemo(() => [
    { id: 'nom', header: 'Conducteur', width: 200, accessor: (r) => r.nom, cell: (v) => v || '—' },
    {
      id: 'accuse',
      header: 'Charte accusée',
      width: 220,
      searchable: false,
      accessor: (r) => {
        const acc = (accuses || []).find((a) => a.conducteur === r.id)
        return acc && derniere && acc.version === derniere.version ? 'à jour' : 'à faire'
      },
      cell: (_v, r) => {
        const acc = (accuses || []).find((a) => a.conducteur === r.id)
        const aJour = acc && derniere && acc.version === derniere.version
        if (aJour) {
          return <Badge tone="success">Accusée le {formatDateTime(acc.date_accuse)}</Badge>
        }
        return (
          <Button size="sm" variant="outline" onClick={() => accuser(r.id)} disabled={!derniere}>
            Accuser lecture
          </Button>
        )
      },
    },
  ], [accuses, derniere, accuser])

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-2 rounded-md border border-border px-3 py-2 text-sm">
        <FileCheck className="size-4 text-muted-foreground" aria-hidden="true" />
        {loadingCharte
          ? 'Chargement de la charte…'
          : derniere
            ? `Charte véhicule en vigueur : version ${derniere.version} (publiée le ${formatDate(derniere.date_publication)}).`
            : 'Aucune charte véhicule publiée pour cette société.'}
      </div>
      <ListShell
        title="Accusés de lecture"
        subtitle="Suivi conducteur par conducteur de la charte véhicule en vigueur."
        columns={columns}
        rows={conducteurs}
        loading={loadingAccuses}
        exportName="charte-accuses"
        emptyTitle="Aucun conducteur"
        emptyDescription="Aucun conducteur à suivre."
      />
    </div>
  )
}

export default function ConducteursScreen() {
  // Charge conducteurs + véhicules une fois pour alimenter le formulaire
  // d'affectation (et son contrôle de permis) sans re-fetch par onglet.
  const { data: conducteurs } = useFlotteResource(flotteApi.conducteurs.list, { actif: 'true' })
  const { data: vehicules } = useFlotteResource(flotteApi.vehicules.list, {})

  return (
    <div className="page flex flex-col gap-4">
      <h2 className="font-display text-xl font-semibold tracking-tight">Conducteurs & mobilité</h2>
      <Tabs defaultValue="conducteurs">
        <TabsList className="flex-wrap">
          <TabsTrigger value="conducteurs">Conducteurs</TabsTrigger>
          <TabsTrigger value="affectations">Affectations</TabsTrigger>
          <TabsTrigger value="reservations">Réservations</TabsTrigger>
          <TabsTrigger value="etats">États des lieux</TabsTrigger>
          <TabsTrigger value="charte">Charte véhicule</TabsTrigger>
        </TabsList>
        <TabsContent value="conducteurs"><ConducteursTab /></TabsContent>
        <TabsContent value="affectations">
          <AffectationsTab conducteurs={conducteurs} vehicules={vehicules} />
        </TabsContent>
        <TabsContent value="reservations"><ReservationsTab /></TabsContent>
        <TabsContent value="etats"><EtatsDesLieuxTab /></TabsContent>
        <TabsContent value="charte"><CharteTab conducteurs={conducteurs} /></TabsContent>
      </Tabs>
    </div>
  )
}
