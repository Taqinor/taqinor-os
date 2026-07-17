import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ShieldCheck, Plus } from 'lucide-react'
import assurancesApi from './assurancesApi'
import { Badge, Button, Segmented } from '../../ui'
import { ListShell } from '../../ui/module'
import { formatMAD, formatDate } from '../../lib/format'
import { POLICE_TYPES, POLICE_STATUS, toneEcheance, joursAvant } from './status'

/* ============================================================================
   NTASS25 — Écran `/assurances` : liste des polices d'assurance d'entreprise.
   ----------------------------------------------------------------------------
   Coquille de liste UX1 : filtres par type + statut, badge d'échéance coloré
   (rouge < 7 j, ambre < 30 j), prime annuelle (formatMAD — jamais de prix
   d'achat/marge), pastille de statut. Le clic ouvre la fiche police (NTASS26).
   ========================================================================== */

const STATUT_FILTERS = [
  { value: 'tous', label: 'Tous' },
  ...Object.entries(POLICE_STATUS).map(([value, v]) => ({ value, label: v.label })),
]
const TYPE_FILTERS = [{ value: 'tous', label: 'Tous types' }, ...POLICE_TYPES]

export default function PolicesList() {
  const navigate = useNavigate()
  const [polices, setPolices] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [statutFilter, setStatutFilter] = useState('tous')
  const [typeFilter, setTypeFilter] = useState('tous')

  const load = () => {
    setLoading(true)
    setError(null)
    assurancesApi
      .getPolices()
      .then((res) => setPolices(Array.isArray(res.data) ? res.data : (res.data?.results ?? [])))
      .catch(() => setError('Impossible de charger les polices.'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount loading state
    load()
  }, [])

  const visible = useMemo(() => polices.filter((p) => {
    if (statutFilter !== 'tous' && p.statut !== statutFilter) return false
    if (typeFilter !== 'tous' && p.type_police !== typeFilter) return false
    return true
  }), [polices, statutFilter, typeFilter])

  const columns = useMemo(() => [
    {
      id: 'assureur',
      header: 'Assureur',
      width: 200,
      accessor: (p) => p.assureur_nom || '',
      cell: (v) => <span className="font-medium">{v || '—'}</span>,
    },
    {
      id: 'type',
      header: 'Type',
      width: 150,
      accessor: (p) => p.type_police_display || p.type_police || '',
    },
    {
      id: 'numero',
      header: 'N° police',
      width: 140,
      accessor: (p) => p.numero_police || '',
      cell: (v) => <span className="font-mono text-xs">{v || '—'}</span>,
    },
    {
      id: 'echeance',
      header: 'Échéance',
      width: 150,
      accessor: (p) => p.date_echeance || '',
      cell: (v) => {
        if (!v) return <span className="text-muted-foreground">—</span>
        const j = joursAvant(v)
        return (
          <Badge tone={toneEcheance(v)}>
            {formatDate(v)}
            {j != null && j >= 0 && j < 30 ? ` · J-${j}` : ''}
            {j != null && j < 0 ? ' · échu' : ''}
          </Badge>
        )
      },
    },
    {
      id: 'prime',
      header: 'Prime annuelle',
      align: 'right',
      width: 140,
      accessor: (p) => Number(p.prime_annuelle_ht ?? 0),
      cell: (_v, p) => (
        <span className="font-medium tabular-nums">
          {formatMAD(p.prime_annuelle_ht ?? 0)}
        </span>
      ),
    },
    {
      id: 'statut',
      header: 'Statut',
      width: 120,
      accessor: (p) => p.statut || '',
      cell: (v) => {
        const s = POLICE_STATUS[v]
        return s ? <Badge tone={s.tone}>{s.label}</Badge> : <span>—</span>
      },
    },
  ], [])

  return (
    <ListShell
      title="Polices d'assurance"
      subtitle="Registre des polices d'entreprise : RC pro, décennale, multirisque, cyber, homme-clé…"
      actions={(
        <Button onClick={() => navigate('/assurances/nouvelle')}>
          <Plus /> Nouvelle police
        </Button>
      )}
      breadcrumbs={[{ label: 'Assurances' }]}
      columns={columns}
      rows={visible}
      loading={loading}
      error={error}
      searchable
      searchPlaceholder="Rechercher assureur, numéro…"
      exportName="polices-assurance"
      emptyTitle="Aucune police"
      emptyDescription="Aucune police ne correspond à ces filtres."
      onRowClick={(p) => navigate(`/assurances/${p.id}`)}
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
          <ShieldCheck className="size-3.5" aria-hidden="true" />
          {visible.length} police(s) affichée(s)
        </p>
      )}
    </ListShell>
  )
}
