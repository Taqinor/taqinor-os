import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Lightbulb, Plus, Eye, ThumbsUp, Download, Tag as TagIcon } from 'lucide-react'
import { ListShell } from '../../ui/module'
import { Badge, Button, toast } from '../../ui'
import { formatDate } from '../../lib/format'
import innovationApi from '../../api/innovationApi'
import { downloadBlob } from '../../utils/downloadBlob'
import { STATUT_MAP, StatutIdeePill } from './innovationStatus'
import FilterSelect from './FilterSelect'

/* ============================================================================
   NTIDE4 — Liste des idées + filtres (statut/contexte), tri par votes/date.
   NTIDE13 — Actions en masse (admin) : changer statut / tag / exporter la
   sélection. Ouverte à TOUT utilisateur connecté (« logged-in users only ») ;
   les actions en masse restent réservées au palier admin/responsable côté
   serveur (403 affiché en toast si le rôle est insuffisant).
   ========================================================================== */

const STATUT_FILTER_OPTIONS = [
  { value: '', label: 'Tous les statuts' },
  ...Object.entries(STATUT_MAP).map(([value, v]) => ({ value, label: v.label })),
]

export default function IdeesPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [idees, setIdees] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  // NTIDE6 — drill-down depuis le tableau de bord (?statut=/?contexte=).
  const [statutFilter, setStatutFilter] = useState(() => searchParams.get('statut') || '')
  const [contexteFilter, setContexteFilter] = useState(() => searchParams.get('contexte') || '')

  const load = () => {
    setLoading(true)
    setError(null)
    innovationApi.list()
      .then((res) => {
        setIdees(Array.isArray(res.data) ? res.data : (res.data?.results ?? []))
      })
      .catch(() => setError('Impossible de charger les idées.'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount
    load()
  }, [])

  const contextes = useMemo(
    () => Array.from(new Set(idees.map((i) => i.contexte).filter(Boolean))).sort(),
    [idees],
  )

  const rows = useMemo(() => idees.filter((i) =>
    (!statutFilter || i.statut === statutFilter)
    && (!contexteFilter || i.contexte === contexteFilter),
  ), [idees, statutFilter, contexteFilter])

  const columns = useMemo(() => [
    {
      id: 'titre',
      header: 'Titre',
      width: 260,
      accessor: (i) => i.titre,
      cell: (value) => <span className="font-medium">{value || '—'}</span>,
    },
    {
      id: 'auteur',
      header: 'Auteur',
      width: 140,
      accessor: (i) => i.auteur_nom || '',
      cell: (value) => value || <span className="text-muted-foreground">—</span>,
    },
    {
      id: 'contexte',
      header: 'Contexte',
      width: 120,
      accessor: (i) => i.contexte || '',
      cell: (value) => (value
        ? <Badge tone="neutral">{value}</Badge>
        : <span className="text-muted-foreground">—</span>),
    },
    {
      id: 'statut',
      header: 'Statut',
      width: 120,
      accessor: (i) => i.statut,
      cell: (value) => <StatutIdeePill status={value} />,
    },
    {
      id: 'votes',
      header: 'Votes',
      width: 90,
      align: 'right',
      numeric: true,
      searchable: false,
      accessor: (i) => Number(i.votes_count ?? 0),
      cell: (value) => (
        <span className="inline-flex items-center gap-1 font-medium tabular-nums">
          <ThumbsUp className="size-3.5" aria-hidden="true" /> {value}
        </span>
      ),
    },
    {
      id: 'date',
      header: 'Proposée',
      width: 110,
      align: 'right',
      searchable: false,
      accessor: (i) => i.date_creation || '',
      cell: (value) => (
        <span className="text-muted-foreground">{value ? formatDate(value) : '—'}</span>
      ),
    },
  ], [])

  const rowActions = (i) => [
    { id: 'view', label: 'Ouvrir', icon: Eye, onClick: () => navigate(`/innovation/idees/${i.id}`) },
  ]

  const bulkActions = (selectedRows, _keys, clearSelection) => [
    {
      id: 'set_statut_examinee',
      label: 'Marquer « Examinée »',
      onClick: () => runBulk({ action: 'set_statut', statut: 'examinee' }, selectedRows, clearSelection),
    },
    {
      id: 'set_statut_retenue',
      label: 'Marquer « Retenue »',
      onClick: () => runBulk({ action: 'set_statut', statut: 'retenue' }, selectedRows, clearSelection),
    },
    {
      id: 'set_statut_fermee',
      label: 'Marquer « Fermée »',
      onClick: () => runBulk({ action: 'set_statut', statut: 'fermee' }, selectedRows, clearSelection),
    },
    {
      id: 'add_tag',
      label: 'Ajouter un tag…',
      icon: TagIcon,
      separatorBefore: true,
      onClick: () => {
        const tag = window.prompt('Nom du tag à appliquer :')
        if (tag && tag.trim()) runBulk({ action: 'add_tag', tag: tag.trim() }, selectedRows, clearSelection)
      },
    },
    {
      id: 'export',
      label: 'Exporter la sélection (.xlsx)',
      icon: Download,
      onClick: () => runBulk({ action: 'export' }, selectedRows, clearSelection),
    },
  ]

  const runBulk = async (body, selectedRows, clearSelection) => {
    const ids = selectedRows.map((r) => r.id)
    if (!ids.length) { toast.error('Sélectionnez au moins une idée.'); return }
    try {
      const resp = await innovationApi.bulk({ ...body, ids })
      if (body.action === 'export') {
        downloadBlob(resp.data, 'idees.xlsx')
        toast.success('Export téléchargé.')
      } else {
        toast.success('Action en masse appliquée.')
        clearSelection?.()
        load()
      }
    } catch (err) {
      toast.error(err?.response?.status === 403
        ? 'Action réservée au palier admin/responsable.'
        : 'Action en masse impossible.')
    }
  }

  const contexteOptions = [
    { value: '', label: 'Tous les contextes' },
    ...contextes.map((c) => ({ value: c, label: c })),
  ]

  const filters = (
    <div className="flex flex-wrap items-center gap-2">
      <FilterSelect
        value={statutFilter}
        onChange={setStatutFilter}
        options={STATUT_FILTER_OPTIONS}
        aria-label="Filtrer par statut"
      />
      {contextes.length > 0 && (
        <FilterSelect
          value={contexteFilter}
          onChange={setContexteFilter}
          options={contexteOptions}
          aria-label="Filtrer par contexte"
        />
      )}
    </div>
  )

  return (
    <div className="page flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="inline-flex items-center gap-2 font-display text-xl font-semibold tracking-tight">
          <Lightbulb className="size-5" aria-hidden="true" />
          Boîte à idées
        </h1>
        <Button onClick={() => navigate('/innovation/proposer')}>
          <Plus /> Proposer une idée
        </Button>
      </div>

      <ListShell
        title="Idées proposées"
        filters={filters}
        columns={columns}
        rows={rows}
        loading={loading}
        error={error}
        onRowClick={(i) => navigate(`/innovation/idees/${i.id}`)}
        rowActions={rowActions}
        bulkActions={bulkActions}
        selectable
        searchable
        searchPlaceholder="Rechercher (titre)…"
        exportName="innovation-idees"
        emptyTitle="Aucune idée"
        emptyDescription="Aucune idée ne correspond à ces filtres."
        emptyAction={<Button size="sm" onClick={() => navigate('/innovation/proposer')}><Plus className="size-4" /> Proposer une idée</Button>}
      />
    </div>
  )
}
