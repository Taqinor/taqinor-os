import { useMemo, useState } from 'react'
import { Segmented } from '../../ui'
import { ListShell } from '../../ui/module'
import installationsApi from '../../api/installationsApi'
import { formatDate, formatNumber } from '../../lib/format'
import useMagasinResource from './useMagasinResource'
import { PutAwayStatutPill } from './statusPills'

/* ============================================================================
   XSTK1 — Rangement guidé / put-away (`/magasin/rangement`).
   ----------------------------------------------------------------------------
   Liste des opérations de put-away (FG320) : à la confirmation d'une
   réception, le backend suggère un casier (`bin_suggere`) ; le magasinier
   confirme (éventuellement vers un autre casier) via l'action `ranger`.
   ========================================================================== */

const STATUT_FILTERS = [
  { value: '', label: 'Tous statuts' },
  { value: 'a_ranger', label: 'À ranger' },
  { value: 'range', label: 'Rangé' },
]

export default function PutAwayScreen() {
  const [statut, setStatut] = useState('a_ranger')
  const [busyId, setBusyId] = useState(null)
  const [feedback, setFeedback] = useState(null)

  const params = useMemo(() => (statut ? { statut } : {}), [statut])

  const { data, loading, error, reload, setData } = useMagasinResource(
    installationsApi.getPutAways, params, [statut],
  )

  const ranger = async (row) => {
    setBusyId(row.id)
    setFeedback(null)
    try {
      const res = await installationsApi.rangerPutAway(row.id)
      setData((prev) => prev.map((r) => (r.id === row.id ? res.data : r)))
      setFeedback({ tone: 'success', message: `Rangement confirmé pour ${row.produit_nom || 'ce produit'}.` })
    } catch (err) {
      setFeedback({
        tone: 'error',
        message: err?.response?.data?.bin || err?.response?.data?.detail || 'Rangement impossible.',
      })
    } finally {
      setBusyId(null)
      reload()
    }
  }

  const columns = useMemo(() => [
    {
      id: 'produit',
      header: 'Produit',
      width: 220,
      accessor: (r) => r.produit_nom || `Produit ${r.produit}`,
      cell: (v) => v || '—',
    },
    {
      id: 'quantite',
      header: 'Qté',
      align: 'right',
      numeric: true,
      width: 90,
      accessor: (r) => Number(r.quantite ?? 0),
      cell: (v) => formatNumber(v),
    },
    {
      id: 'bin_suggere',
      header: 'Casier suggéré',
      width: 150,
      accessor: (r) => r.bin_suggere_code,
      cell: (v) => (v ? <span className="font-mono">{v}</span> : '—'),
    },
    {
      id: 'bin_effectif',
      header: 'Casier effectif',
      width: 150,
      accessor: (r) => r.bin_effectif_code,
      cell: (v) => (v ? <span className="font-mono">{v}</span> : '—'),
    },
    {
      id: 'reference_reception',
      header: 'Réception',
      width: 150,
      accessor: (r) => r.reference_reception,
      cell: (v) => v || '—',
    },
    {
      id: 'statut',
      header: 'Statut',
      width: 120,
      accessor: (r) => r.statut,
      cell: (v) => <PutAwayStatutPill status={v} />,
    },
    {
      id: 'date_creation',
      header: 'Créé le',
      width: 120,
      accessor: (r) => r.date_creation,
      cell: (v) => (v ? formatDate(v) : '—'),
    },
  ], [])

  const rowActions = useMemo(() => (row) => {
    if (row.statut !== 'a_ranger') return []
    return [
      {
        id: 'ranger',
        label: busyId === row.id ? 'Rangement…' : 'Ranger',
        onClick: () => ranger(row),
      },
    ]
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [busyId])

  const filters = (
    <Segmented options={STATUT_FILTERS} value={statut} onChange={setStatut} aria-label="Filtrer par statut" />
  )

  return (
    <div className="page flex flex-col gap-3">
      {feedback && (
        <p
          role="status"
          className={feedback.tone === 'error' ? 'text-sm text-destructive' : 'text-sm text-success'}
        >
          {feedback.message}
        </p>
      )}
      <ListShell
        title="Rangement guidé (put-away)"
        subtitle="Suggestion de casier à la réception — confirmer le rangement effectif."
        filters={filters}
        columns={columns}
        rows={data}
        loading={loading}
        error={error}
        rowActions={rowActions}
        exportName="putaways"
        emptyTitle="Aucun rangement"
        emptyDescription="Aucune opération de rangement pour ce filtre."
      />
    </div>
  )
}
