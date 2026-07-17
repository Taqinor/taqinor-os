import { useEffect, useMemo, useState } from 'react'
import { ShieldAlert } from 'lucide-react'
import assurancesApi from './assurancesApi'
import { Badge, Button, Segmented } from '../../ui'
import { ListShell } from '../../ui/module'
import { formatMAD, formatDate } from '../../lib/format'
import { SINISTRE_STATUS, SINISTRE_TYPES } from './status'

/* ============================================================================
   NTASS27 — Écran sinistres transverses + suivi indemnisation.
   ----------------------------------------------------------------------------
   Liste filtrable par statut (declare/en_expertise/indemnise/refuse/clos), avec
   bloc indemnisation (réclamé/franchise/indemnisé/reste à charge) sur la fiche
   sélectionnée et bouton « Marquer contesté » (NTASS16). Montants client-safe.
   ========================================================================== */

const STATUT_FILTERS = [
  { value: 'tous', label: 'Tous' },
  ...Object.entries(SINISTRE_STATUS).map(([value, v]) => ({ value, label: v.label })),
]
const TYPE_LABEL = Object.fromEntries(SINISTRE_TYPES.map((t) => [t.value, t.label]))

export default function SinistresPage() {
  const [sinistres, setSinistres] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [statutFilter, setStatutFilter] = useState('tous')
  const [selected, setSelected] = useState(null)

  const load = () => {
    setLoading(true)
    setError(null)
    assurancesApi
      .getSinistres()
      .then((res) => setSinistres(Array.isArray(res.data) ? res.data : (res.data?.results ?? [])))
      .catch(() => setError('Impossible de charger les sinistres.'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount loading state
    load()
  }, [])

  const visible = useMemo(() => sinistres.filter(
    (s) => statutFilter === 'tous' || s.statut === statutFilter,
  ), [sinistres, statutFilter])

  const marquerConteste = (id) => {
    assurancesApi.marquerSinistreConteste(id).then(load)
  }

  const columns = useMemo(() => [
    {
      id: 'reference',
      header: 'N° dossier',
      width: 140,
      accessor: (s) => s.numero_dossier || '',
      cell: (v) => <span className="font-mono text-xs">{v || '—'}</span>,
    },
    {
      id: 'type',
      header: 'Type',
      width: 170,
      accessor: (s) => TYPE_LABEL[s.type_sinistre] || s.type_sinistre || '',
    },
    {
      id: 'survenance',
      header: 'Survenance',
      width: 120,
      accessor: (s) => s.date_survenance || '',
      cell: (v) => (v ? formatDate(v) : '—'),
    },
    {
      id: 'estime',
      header: 'Dégâts estimés',
      align: 'right',
      width: 140,
      accessor: (s) => Number(s.montant_estime_degats ?? 0),
      cell: (_v, s) => (
        <span className="tabular-nums">{formatMAD(s.montant_estime_degats ?? 0)}</span>
      ),
    },
    {
      id: 'statut',
      header: 'Statut',
      width: 130,
      accessor: (s) => s.statut || '',
      cell: (v, s) => {
        const st = SINISTRE_STATUS[v]
        return (
          <span className="flex items-center gap-1">
            {st ? <Badge tone={st.tone}>{st.label}</Badge> : '—'}
            {s.conteste && <Badge tone="red">Contesté</Badge>}
          </span>
        )
      },
    },
  ], [])

  return (
    <ListShell
      title="Sinistres transverses"
      subtitle="Déclarations hors véhicule : dommage, RC, décennale, cyber, vol, incendie… Suivi jusqu'à l'indemnisation."
      breadcrumbs={[{ label: 'Assurances' }, { label: 'Sinistres' }]}
      columns={columns}
      rows={visible}
      loading={loading}
      error={error}
      searchable
      searchPlaceholder="Rechercher n° dossier, type…"
      exportName="sinistres-assurance"
      emptyTitle="Aucun sinistre"
      emptyDescription="Aucun sinistre ne correspond à ce filtre."
      onRowClick={(s) => setSelected(s)}
    >
      <div className="flex flex-wrap items-center gap-2">
        <Segmented
          options={STATUT_FILTERS}
          value={statutFilter}
          onChange={setStatutFilter}
          aria-label="Filtrer par statut"
        />
        {error && (
          <Button variant="outline" size="sm" onClick={load}>Réessayer</Button>
        )}
      </div>
      {selected && (
        <div className="rounded-lg border p-3 text-sm">
          <div className="mb-2 flex items-center justify-between">
            <span className="font-semibold">
              {selected.numero_dossier} — indemnisation
            </span>
            {!selected.conteste && selected.statut === 'refuse' && (
              <Button size="sm" variant="outline" onClick={() => marquerConteste(selected.id)}>
                Marquer contesté
              </Button>
            )}
          </div>
          <IndemnisationBloc sinistreId={selected.id} />
        </div>
      )}
      {!error && (
        <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <ShieldAlert className="size-3.5" aria-hidden="true" />
          {visible.length} sinistre(s) affiché(s)
        </p>
      )}
    </ListShell>
  )
}

function IndemnisationBloc({ sinistreId }) {
  const [data, setData] = useState(null)
  useEffect(() => {
    assurancesApi.getSinistre(sinistreId)
      .then((res) => setData(res.data?.indemnisation ?? null))
      .catch(() => setData(null))
  }, [sinistreId])

  if (!data) {
    return <p className="text-muted-foreground">Aucune indemnisation enregistrée.</p>
  }
  return (
    <dl className="grid grid-cols-2 gap-x-4 gap-y-1">
      <dt className="text-muted-foreground">Réclamé</dt>
      <dd className="tabular-nums text-right">{formatMAD(data.montant_reclame)}</dd>
      <dt className="text-muted-foreground">Franchise</dt>
      <dd className="tabular-nums text-right">{formatMAD(data.franchise_appliquee)}</dd>
      <dt className="text-muted-foreground">Indemnisé</dt>
      <dd className="tabular-nums text-right">{formatMAD(data.montant_indemnise)}</dd>
      <dt className="font-medium">Reste à charge</dt>
      <dd className="font-medium tabular-nums text-right">{formatMAD(data.reste_a_charge)}</dd>
    </dl>
  )
}
