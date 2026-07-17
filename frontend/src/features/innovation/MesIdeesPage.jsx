import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useSelector } from 'react-redux'
import { User, ThumbsUp, Eye } from 'lucide-react'
import { ListShell } from '../../ui/module'
import { Badge } from '../../ui'
import { formatDate } from '../../lib/format'
import innovationApi from '../../api/innovationApi'
import { STATUT_MAP, StatutIdeePill } from './innovationStatus'

/* ============================================================================
   NTIDE15 — Page « Mes idées » (route dédiée /innovation/mes-idees) : les
   idées PROPOSÉES par l'utilisateur connecté (filtre ``owner``, déjà exposé
   par ``IdeeViewSet.get_queryset``, NTIDE4), avec leur statut/votes. Tri par
   date/votes en cliquant l'en-tête de colonne (DataTable, comportement
   standard). Drill-down sur le détail (NTIDE5).
   ========================================================================== */

export default function MesIdeesPage() {
  const navigate = useNavigate()
  const currentUser = useSelector((s) => s.auth.user)
  const [idees, setIdees] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!currentUser?.id) return
    setLoading(true)
    setError(null)
    innovationApi.list({ owner: currentUser.id })
      .then((res) => {
        setIdees(Array.isArray(res.data) ? res.data : (res.data?.results ?? []))
      })
      .catch(() => setError('Impossible de charger vos idées.'))
      .finally(() => setLoading(false))
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount
  }, [currentUser?.id])

  const columns = useMemo(() => [
    {
      id: 'titre',
      header: 'Titre',
      width: 280,
      accessor: (i) => i.titre,
      cell: (value, row) => (
        <span className="inline-flex items-center gap-2 font-medium">
          {value || '—'}
          {row.draft && <Badge tone="warning">Brouillon</Badge>}
        </span>
      ),
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

  return (
    <div className="page flex flex-col gap-6">
      <h1 className="inline-flex items-center gap-2 font-display text-xl font-semibold tracking-tight">
        <User className="size-5" aria-hidden="true" />
        Mes idées
      </h1>

      <ListShell
        title="Idées que vous avez proposées"
        columns={columns}
        rows={idees}
        loading={loading}
        error={error}
        onRowClick={(i) => navigate(`/innovation/idees/${i.id}`)}
        rowActions={rowActions}
        searchable
        searchPlaceholder="Rechercher (titre)…"
        exportName="innovation-mes-idees"
        emptyTitle="Aucune idée proposée"
        emptyDescription="Vous n'avez pas encore proposé d'idée."
      />
    </div>
  )
}
