import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { FileSignature, Plus } from 'lucide-react'
import contratsApi from '../../api/contratsApi'
import { Button, Segmented } from '../../ui'
import { ListShell } from '../../ui/module'
import { formatMAD, formatDate } from '../../lib/format'
import {
  StatutContrat, StatutConfidentialite, CONTRAT_STATUS, CONTRAT_TYPES,
} from './status'

/* ============================================================================
   UX34 — Liste des contrats (cycle de vie CLM).
   ----------------------------------------------------------------------------
   Coquille de liste UX1 : filtres par statut + type, pastilles de statut et de
   confidentialité, montant TTC client-facing (formatMAD — jamais de prix
   d'achat/marge). Le clic ouvre la fiche cycle de vie (UX34 détail).
   ========================================================================== */

const STATUT_FILTERS = [
  { value: 'tous', label: 'Tous' },
  ...Object.entries(CONTRAT_STATUS).map(([value, v]) => ({ value, label: v.label })),
]

const TYPE_FILTERS = [{ value: 'tous', label: 'Tous types' }, ...CONTRAT_TYPES]

export default function ContratsList() {
  const navigate = useNavigate()
  const [contrats, setContrats] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [statutFilter, setStatutFilter] = useState('tous')
  const [typeFilter, setTypeFilter] = useState('tous')

  const load = () => {
    setLoading(true)
    setError(null)
    contratsApi
      .getContrats()
      .then((res) => setContrats(Array.isArray(res.data) ? res.data : (res.data?.results ?? [])))
      .catch(() => setError('Impossible de charger les contrats.'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount loading state
    load()
  }, [])

  const visible = useMemo(() => contrats.filter((c) => {
    if (statutFilter !== 'tous' && c.statut !== statutFilter) return false
    if (typeFilter !== 'tous' && c.type_contrat !== typeFilter) return false
    return true
  }), [contrats, statutFilter, typeFilter])

  const columns = useMemo(() => [
    {
      id: 'reference',
      header: 'Référence',
      width: 150,
      accessor: (c) => c.reference || `#${c.id}`,
      cell: (v) => <span className="font-mono text-xs">{v}</span>,
    },
    {
      id: 'objet',
      header: 'Objet',
      width: 260,
      accessor: (c) => c.objet || '',
      cell: (v) => <span className="font-medium">{v || '—'}</span>,
    },
    {
      id: 'type',
      header: 'Type',
      width: 130,
      accessor: (c) => c.type_contrat_display || c.type_contrat || '',
      cell: (v) => v || '—',
    },
    {
      id: 'statut',
      header: 'Statut',
      width: 150,
      accessor: (c) => c.statut,
      cell: (v) => <StatutContrat status={v} />,
    },
    {
      id: 'confidentialite',
      header: 'Confidentialité',
      width: 140,
      accessor: (c) => c.confidentialite,
      cell: (v) => <StatutConfidentialite status={v} />,
    },
    {
      id: 'montant',
      header: 'Montant',
      align: 'right',
      numeric: true,
      width: 140,
      searchable: false,
      accessor: (c) => Number(c.montant ?? 0),
      cell: (_v, c) => (c.montant != null
        ? <span className="font-medium tabular-nums">{formatMAD(c.montant)}</span>
        : <span className="text-muted-foreground">—</span>),
      exportValue: (c) => Number(c.montant ?? 0),
    },
    {
      id: 'date_fin',
      header: 'Échéance',
      align: 'right',
      width: 120,
      searchable: false,
      accessor: (c) => c.date_fin || '',
      cell: (v) => (v ? formatDate(v) : <span className="text-muted-foreground">—</span>),
    },
  ], [])

  return (
    <ListShell
      title="Contrats"
      subtitle="Cycle de vie des contrats : brouillon → approbation → signé → actif → suspendu → résilié → expiré."
      actions={(
        <Button onClick={() => navigate('/contrats/modeles')}>
          <Plus /> Nouveau contrat
        </Button>
      )}
      breadcrumbs={[{ label: 'Contrats' }]}
      columns={columns}
      rows={visible}
      loading={loading}
      error={error}
      searchable
      searchPlaceholder="Rechercher référence, objet…"
      exportName="contrats"
      emptyTitle="Aucun contrat"
      emptyDescription="Aucun contrat ne correspond à ces filtres."
      emptyAction={<Button size="sm" onClick={() => navigate('/contrats/modeles')}><Plus className="size-4" /> Nouveau contrat</Button>}
      onRowClick={(c) => navigate(`/contrats/${c.id}`)}
    >
      <div className="flex flex-wrap items-center gap-2">
        <Segmented
          options={STATUT_FILTERS}
          value={statutFilter}
          onChange={setStatutFilter}
          aria-label="Filtrer par statut"
        />
        <Segmented
          options={TYPE_FILTERS}
          value={typeFilter}
          onChange={setTypeFilter}
          aria-label="Filtrer par type"
        />
        {error && (
          <Button variant="outline" size="sm" onClick={load}>Réessayer</Button>
        )}
      </div>
      {!error && (
        <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <FileSignature className="size-3.5" aria-hidden="true" />
          {visible.length} contrat(s) affiché(s)
        </p>
      )}
    </ListShell>
  )
}
