import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Lightbulb, Eye, ThumbsUp } from 'lucide-react'
import { ListShell } from '../../ui/module'
import { Badge } from '../../ui'
import { formatDate } from '../../lib/format'
import innovationApi from '../../api/innovationApi'
import { STATUT_MAP, StatutIdeePill } from './innovationStatus'
import FilterSelect from './FilterSelect'

/* ============================================================================
   NTIDE4 — Liste des idées + filtres (statut/contexte), tri par votes/date.
   Ouverte à TOUT utilisateur connecté (« logged-in users only »).
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
        searchable
        searchPlaceholder="Rechercher (titre)…"
        exportName="innovation-idees"
        emptyTitle="Aucune idée"
        emptyDescription="Aucune idée ne correspond à ces filtres."
      />
    </div>
  )
}
