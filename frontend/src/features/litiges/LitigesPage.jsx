import { useEffect, useMemo, useState } from 'react'
import {
  Gavel, Plus, Eye, Pencil, Trash2, Clock, FileWarning, Coins, BarChart3,
} from 'lucide-react'
import { ListShell, ModuleDashboard } from '../../ui/module'
import { Button, Badge, Segmented, toast } from '../../ui'
import { ConfirmDialog } from '../../ui/ConfirmDialog'
import { formatMAD, formatDate } from '../../lib/format'
import litigesApi from '../../api/litigesApi'
import {
  STATUT_MAP, GRAVITE_MAP, TYPE_MAP,
  StatutReclamationPill, GraviteReclamationPill,
} from './litigesStatus'
import ReclamationDetail from './ReclamationDetail'
import ReclamationEditor from './ReclamationEditor'
import AnalyseConcurrents from './AnalyseConcurrents'
import FilterSelect from './FilterSelect'

/* ============================================================================
   UX44 — Litiges & réclamations (apps/litiges).
   ----------------------------------------------------------------------------
   Cockpit (ModuleDashboard : ouverts, montant contesté, délai moyen) au-dessus
   du registre des réclamations (type/gravité/statut, montant contesté, blocage
   des relances). Un onglet « Analyse concurrents » expose l'intelligence sur
   deals perdus. Accès réservé responsable/admin (gaté aussi par la route).
   ========================================================================== */

const STATUT_FILTER_OPTIONS = [
  { value: '', label: 'Tous les statuts' },
  ...Object.entries(STATUT_MAP).map(([value, v]) => ({ value, label: v.label })),
]
const GRAVITE_FILTER_OPTIONS = [
  { value: '', label: 'Toutes gravités' },
  ...Object.entries(GRAVITE_MAP).map(([value, v]) => ({ value, label: v.label })),
]

const VUES = [
  { value: 'registre', label: 'Registre' },
  { value: 'analyse', label: 'Analyse concurrents' },
]

export default function LitigesPage() {
  const [vue, setVue] = useState('registre')
  const [reclamations, setReclamations] = useState([])
  const [cockpit, setCockpit] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [statutFilter, setStatutFilter] = useState('')
  const [graviteFilter, setGraviteFilter] = useState('')

  const [selected, setSelected] = useState(null)
  const [editing, setEditing] = useState(null)
  // VX244 — un litige est un DOSSIER LÉGAL : suppression à confirmation
  // tapée (severity="high"), plus jamais un `window.confirm` natif.
  const [pendingDelete, setPendingDelete] = useState(null)
  const [deleting, setDeleting] = useState(false)

  const load = () => {
    setLoading(true)
    setError(null)
    Promise.all([litigesApi.list(), litigesApi.tableauBord()])
      .then(([listRes, cockpitRes]) => {
        setReclamations(
          Array.isArray(listRes.data) ? listRes.data : (listRes.data?.results ?? []))
        setCockpit(cockpitRes.data)
      })
      .catch(() => setError('Impossible de charger les réclamations.'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount
    load()
  }, [])

  // Filtres appliqués côté client (statut/gravité), la recherche reste au DataTable.
  const rows = useMemo(() => reclamations.filter((r) =>
    (!statutFilter || r.statut === statutFilter)
    && (!graviteFilter || r.gravite === graviteFilter),
  ), [reclamations, statutFilter, graviteFilter])

  const openDetail = (r) => setSelected(r)
  const openEditor = (r) => setEditing(r ?? {})
  const closeAll = () => { setSelected(null); setEditing(null) }

  const handleRemove = (r) => setPendingDelete(r)

  const confirmRemove = async () => {
    if (!pendingDelete) return
    setDeleting(true)
    try {
      await litigesApi.remove(pendingDelete.id)
      toast.success('Réclamation supprimée.')
      setPendingDelete(null)
      closeAll()
      load()
    } catch { toast.error('Suppression impossible.') } finally { setDeleting(false) }
  }

  const stats = useMemo(() => {
    if (!cockpit) return []
    const delai = cockpit.delai_resolution_moyen_jours
    return [
      {
        label: 'Réclamations ouvertes',
        value: cockpit.ouvertes ?? 0,
        hint: `${cockpit.en_traitement ?? 0} en traitement`,
        icon: FileWarning,
      },
      {
        label: 'Montant contesté',
        value: formatMAD(cockpit.montant_conteste_total),
        icon: Coins,
      },
      {
        label: 'Délai de résolution moyen',
        value: delai != null ? `${delai} j` : '—',
        hint: `${cockpit.nb_resolues_avec_delai ?? 0} résolue(s) mesurée(s)`,
        icon: Clock,
      },
      {
        label: 'Total réclamations',
        value: cockpit.total ?? 0,
        hint: `${cockpit.resolues ?? 0} résolue(s) · ${cockpit.rejetees ?? 0} rejetée(s)`,
        icon: BarChart3,
      },
    ]
  }, [cockpit])

  const columns = useMemo(() => [
    {
      id: 'reference',
      header: 'Référence',
      width: 130,
      accessor: (r) => r.reference || '',
      cell: (value) => (value
        ? <span className="font-mono text-xs">{value}</span>
        : <span className="text-muted-foreground">—</span>),
    },
    {
      id: 'objet',
      header: 'Objet',
      width: 240,
      accessor: (r) => r.objet,
      cell: (value) => <span className="font-medium">{value || '—'}</span>,
    },
    {
      id: 'type',
      header: 'Type',
      width: 120,
      accessor: (r) => TYPE_MAP[r.type_reclamation] || r.type_reclamation || '',
      cell: (value) => <Badge tone="neutral">{value || '—'}</Badge>,
    },
    {
      id: 'gravite',
      header: 'Gravité',
      width: 110,
      accessor: (r) => r.gravite,
      cell: (value) => <GraviteReclamationPill status={value} />,
    },
    {
      id: 'statut',
      header: 'Statut',
      width: 130,
      accessor: (r) => r.statut,
      cell: (value) => <StatutReclamationPill status={value} />,
    },
    {
      id: 'montant',
      header: 'Montant contesté',
      width: 150,
      align: 'right',
      numeric: true,
      searchable: false,
      accessor: (r) => Number(r.montant_conteste ?? 0),
      cell: (_v, r) => {
        const m = Number(r.montant_conteste ?? 0)
        return m ? <span className="font-medium">{formatMAD(m)}</span>
          : <span className="text-muted-foreground">—</span>
      },
    },
    {
      id: 'relances',
      header: 'Relances',
      width: 120,
      searchable: false,
      accessor: (r) => (r.bloque_relances ? 'bloquees' : 'actives'),
      cell: (_v, r) => (r.bloque_relances
        ? <Badge tone="warning">Bloquées</Badge>
        : <Badge tone="neutral">Actives</Badge>),
    },
    {
      id: 'date',
      header: 'Créée',
      width: 110,
      align: 'right',
      searchable: false,
      accessor: (r) => r.date_creation || '',
      cell: (value) => (
        <span className="text-muted-foreground">{value ? formatDate(value) : '—'}</span>
      ),
    },
  ], [])

  const rowActions = (r) => [
    { id: 'view', label: 'Ouvrir', icon: Eye, onClick: () => openDetail(r) },
    { id: 'edit', label: 'Éditer', icon: Pencil, onClick: () => openEditor(r) },
    {
      id: 'delete', label: 'Supprimer', icon: Trash2,
      destructive: true, separatorBefore: true,
      onClick: () => handleRemove(r),
    },
  ]

  const filters = (
    <div className="flex flex-wrap items-center gap-2">
      <FilterSelect
        value={statutFilter}
        onChange={setStatutFilter}
        options={STATUT_FILTER_OPTIONS}
        aria-label="Filtrer par statut"
      />
      <FilterSelect
        value={graviteFilter}
        onChange={setGraviteFilter}
        options={GRAVITE_FILTER_OPTIONS}
        aria-label="Filtrer par gravité"
      />
    </div>
  )

  // ── Éditeur ──
  if (editing) {
    return (
      <ReclamationEditor
        reclamation={editing.id ? editing : null}
        onCancel={closeAll}
        onSaved={() => { closeAll(); load() }}
      />
    )
  }

  // ── Détail (chatter + transitions) ──
  if (selected) {
    return (
      <ReclamationDetail
        reclamationId={selected.id}
        onBack={closeAll}
        onEdit={() => openEditor(selected)}
        onChanged={load}
      />
    )
  }

  return (
    <div className="page flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="inline-flex items-center gap-2 font-display text-xl font-semibold tracking-tight">
          <Gavel className="size-5" aria-hidden="true" />
          Litiges &amp; réclamations
        </h1>
        <div className="flex items-center gap-2">
          <Segmented options={VUES} value={vue} onChange={setVue} aria-label="Vue" />
          <Button onClick={() => openEditor(null)}>
            <Plus /> Nouvelle réclamation
          </Button>
        </div>
      </div>

      {/* Cockpit toujours visible (ModuleDashboard). */}
      <ModuleDashboard stats={stats} loading={loading && !cockpit} error={error} />

      {vue === 'analyse' ? (
        <AnalyseConcurrents />
      ) : (
        <ListShell
          title="Registre des réclamations"
          filters={filters}
          columns={columns}
          rows={rows}
          loading={loading}
          error={error}
          onRowClick={openDetail}
          rowActions={rowActions}
          searchable
          searchPlaceholder="Rechercher (référence, objet, description)…"
          exportName="litiges-reclamations"
          emptyTitle="Aucune réclamation"
          emptyDescription="Aucune réclamation ne correspond à ces filtres."
        />
      )}

      <ConfirmDialog
        open={!!pendingDelete}
        onOpenChange={(o) => { if (!o) setPendingDelete(null) }}
        severity="high"
        title="Suppression définitive"
        description="Ce dossier (réclamation, échanges, pièces jointes) sera définitivement supprimé. Cette action est irréversible."
        confirmText={pendingDelete?.objet}
        confirmLabel="Supprimer définitivement"
        loading={deleting}
        onConfirm={confirmRemove}
      />
    </div>
  )
}
