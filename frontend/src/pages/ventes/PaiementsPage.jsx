import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Wallet } from 'lucide-react'
import ventesApi from '../../api/ventesApi'
import { formatMAD } from '../../lib/format'
import {
  Card, CardContent, Skeleton, EmptyState, Input, Button,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'
import { Table } from '../reporting/Table'

const dh = (v) => formatMAD(v, { decimals: 2 })

// Modes de paiement (miroir de Paiement.Mode côté backend).
const MODES = [
  { value: 'all', label: 'Tous les modes' },
  { value: 'especes', label: 'Espèces' },
  { value: 'virement', label: 'Virement' },
  { value: 'cheque', label: 'Chèque' },
  { value: 'carte', label: 'Carte bancaire' },
  { value: 'prelevement', label: 'Prélèvement' },
  { value: 'autre', label: 'Autre' },
]

// Encaissements (L512) : liste lecture seule de TOUS les paiements de la
// société (PaiementViewSet), avec filtre par mode/date et lien vers la facture.
export default function PaiementsPage() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  // Filtres d'AFFICHAGE (sur les données déjà chargées — pas d'appel API).
  const [mode, setMode] = useState('all')
  const [du, setDu] = useState('')
  const [au, setAu] = useState('')
  // VX231(b) — filtre client local, reflété dans l'URL (?client=<id>) : cliquer
  // le nom d'un client dans le tableau restreint la liste à ses encaissements
  // (id, jamais de donnée personnelle en clair dans l'URL). Le nom affiché reste
  // la seule info exposée à l'écran.
  const [searchParams, setSearchParams] = useSearchParams()
  const clientFilter = searchParams.get('client') || ''
  const clientFilterNom = useMemo(() => {
    if (!clientFilter) return ''
    const hit = rows.find(p => String(p.client) === clientFilter)
    return hit?.client_nom || ''
  }, [rows, clientFilter])
  const setClientFilter = (id) => {
    setSearchParams(prev => {
      const p = new URLSearchParams(prev)
      if (id) p.set('client', String(id))
      else p.delete('client')
      return p
    }, { replace: true })
  }

  useEffect(() => {
    ventesApi.getPaiements({ ordering: '-date_paiement' })
      .then(r => setRows(r.data.results ?? r.data))
      .catch(() => setError('Impossible de charger les encaissements. Réessayez.'))
      .finally(() => setLoading(false))
  }, [])

  const filtered = useMemo(() => {
    return rows.filter(p => {
      if (mode !== 'all' && p.mode !== mode) return false
      if (clientFilter && String(p.client) !== clientFilter) return false
      const d = p.date_paiement || ''
      if (du && d < du) return false
      if (au && d > au) return false
      return true
    })
  }, [rows, mode, du, au, clientFilter])

  const total = useMemo(
    () => filtered.reduce((s, p) => s + Number(p.montant || 0), 0),
    [filtered],
  )

  return (
    <div className="ui-root page">
      <div className="page-header" style={{ marginBottom: '1.25rem' }}>
        <h2>Encaissements</h2>
      </div>

      {/* VX231(b) — chip du filtre client actif (depuis un clic sur un nom). */}
      {clientFilter && (
        <div className="mb-3 flex items-center gap-2 text-sm">
          <span className="rounded-md border border-border bg-muted/40 px-2 py-1">
            Filtré sur {clientFilterNom || 'un client'}
          </span>
          <Button variant="outline" size="sm" onClick={() => setClientFilter('')}>
            Effacer le filtre client
          </Button>
        </div>
      )}

      {error && (
        <div className="mb-3 rounded border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      )}

      {!loading && rows.length > 0 && (
        <div className="mb-3 flex flex-wrap items-end gap-3">
          <label className="text-sm">
            <span className="mb-1 block text-xs text-muted-foreground">Mode</span>
            <Select value={mode} onValueChange={setMode}>
              <SelectTrigger className="w-44">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {MODES.map(m => (
                  <SelectItem key={m.value} value={m.value}>{m.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </label>
          <label className="text-sm">
            <span className="mb-1 block text-xs text-muted-foreground">Du</span>
            <Input type="date" value={du} onChange={e => setDu(e.target.value)} />
          </label>
          <label className="text-sm">
            <span className="mb-1 block text-xs text-muted-foreground">Au</span>
            <Input type="date" value={au} onChange={e => setAu(e.target.value)} />
          </label>
          {(mode !== 'all' || du || au) && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => { setMode('all'); setDu(''); setAu('') }}
            >
              Effacer les filtres
            </Button>
          )}
        </div>
      )}

      {loading ? (
        <Card>
          <CardContent className="space-y-2 pt-5">
            {Array.from({ length: 5 }).map((unused, i) => (
              <Skeleton key={i} className="h-9 w-full" />
            ))}
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="p-0 sm:p-0">
            {/* P167 — migré vers le moteur de tableau partagé. */}
            <Table
              aria-label="Encaissements"
              getRowKey={(p) => p.id}
              columns={[
                {
                  key: 'facture',
                  header: 'Facture',
                  cell: (p) => (p.facture ? (
                    <Link
                      className="font-medium text-info hover:underline"
                      to={`/ventes/factures?facture=${p.facture}`}
                    >
                      {p.facture_reference || `Facture #${p.facture}`}
                    </Link>
                  ) : '—'),
                },
                {
                  key: 'client',
                  header: 'Client',
                  // VX231(b) — nom cliquable → filtre local ?client=<id>.
                  cell: (p) => (p.client && p.client_nom ? (
                    <button
                      type="button"
                      className="font-medium text-info hover:underline"
                      onClick={() => setClientFilter(p.client)}
                      title={`Filtrer les encaissements de ${p.client_nom}`}
                    >
                      {p.client_nom}
                    </button>
                  ) : (p.client_nom || '—')),
                },
                { key: 'montant', header: 'Montant', align: 'right', cell: (p) => <strong>{dh(p.montant)}</strong> },
                { key: 'date', header: 'Date', cell: (p) => p.date_paiement || '—' },
                { key: 'mode', header: 'Mode', cell: (p) => p.mode_display || p.mode },
                { key: 'par_qui', header: 'Par qui', cell: (p) => p.created_by_username || '—' },
              ]}
              rows={filtered}
              empty={(
                <EmptyState
                  icon={Wallet}
                  title="Aucun encaissement"
                  description={rows.length === 0
                    ? 'Aucun paiement n’a encore été enregistré.'
                    : 'Aucun encaissement ne correspond à ces filtres.'}
                  className="border-0 py-6"
                />
              )}
              footer={filtered.length > 0 && (
                <tr className="border-t border-border font-bold">
                  <td className="px-3 py-2" colSpan={2} data-label="Total">Total ({filtered.length})</td>
                  <td className="px-3 py-2 text-right tabular-nums" data-label="Montant">{dh(total)}</td>
                  <td className="px-3 py-2" colSpan={3} />
                </tr>
              )}
            />
          </CardContent>
        </Card>
      )}
    </div>
  )
}
