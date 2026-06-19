import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Wallet } from 'lucide-react'
import ventesApi from '../../api/ventesApi'
import { formatMAD } from '../../lib/format'
import {
  Card, CardContent, Skeleton, EmptyState, Input, Button,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'

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

  useEffect(() => {
    ventesApi.getPaiements({ ordering: '-date_paiement' })
      .then(r => setRows(r.data.results ?? r.data))
      .catch(() => setError('Impossible de charger les encaissements. Réessayez.'))
      .finally(() => setLoading(false))
  }, [])

  const filtered = useMemo(() => {
    return rows.filter(p => {
      if (mode !== 'all' && p.mode !== mode) return false
      const d = p.date_paiement || ''
      if (du && d < du) return false
      if (au && d > au) return false
      return true
    })
  }, [rows, mode, du, au])

  const total = useMemo(
    () => filtered.reduce((s, p) => s + Number(p.montant || 0), 0),
    [filtered],
  )

  return (
    <div className="ui-root page">
      <div className="page-header" style={{ marginBottom: '1.25rem' }}>
        <h2>Encaissements</h2>
      </div>

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
          <CardContent className="overflow-x-auto p-0 sm:p-0">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Facture</th>
                  <th>Client</th>
                  <th className="ta-right">Montant</th>
                  <th>Date</th>
                  <th>Mode</th>
                  <th>Par qui</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map(p => (
                  <tr key={p.id}>
                    <td data-label="Facture">
                      {p.facture ? (
                        <Link
                          className="font-medium text-info hover:underline"
                          to={`/ventes/factures?facture=${p.facture}`}
                        >
                          {p.facture_reference || `Facture #${p.facture}`}
                        </Link>
                      ) : '—'}
                    </td>
                    <td data-label="Client">{p.client_nom || '—'}</td>
                    <td data-label="Montant" className="ta-right tabular-nums">
                      <strong>{dh(p.montant)}</strong>
                    </td>
                    <td data-label="Date">{p.date_paiement || '—'}</td>
                    <td data-label="Mode">{p.mode_display || p.mode}</td>
                    <td data-label="Par qui">{p.created_by_username || '—'}</td>
                  </tr>
                ))}
                {filtered.length === 0 && (
                  <tr>
                    <td colSpan={6}>
                      <EmptyState
                        icon={Wallet}
                        title="Aucun encaissement"
                        description={rows.length === 0
                          ? 'Aucun paiement n’a encore été enregistré.'
                          : 'Aucun encaissement ne correspond à ces filtres.'}
                        className="border-0 py-6"
                      />
                    </td>
                  </tr>
                )}
              </tbody>
              {filtered.length > 0 && (
                <tfoot>
                  <tr className="font-bold">
                    <td data-label="Total" colSpan={2}>
                      Total ({filtered.length})
                    </td>
                    <td data-label="Montant" className="ta-right tabular-nums">
                      {dh(total)}
                    </td>
                    <td colSpan={3}></td>
                  </tr>
                </tfoot>
              )}
            </table>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
