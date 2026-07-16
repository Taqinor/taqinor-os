import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { FileText, Send, CheckCircle2, Download } from 'lucide-react'
import ventesApi from '../../api/ventesApi'
import reportingApi from '../../api/reportingApi'
import { downloadXlsx } from '../../api/importApi'
import { openPdfBlob } from '../../utils/pdfBlob'
import { formatMAD } from '../../lib/format'
import { Button, Card, CardContent, Segmented, Skeleton, EmptyState } from '../../ui'
import { toast } from '../../ui/confirm'
import { Table } from './Table'
import { StateBlock } from '../../components/StateBlock'

const dh = (v) => formatMAD(v, { decimals: 2 })

// Segments client (filtrage d'AFFICHAGE sur les lignes déjà chargées — aucun
// appel API supplémentaire ; la balance complète reste récupérée en une fois).
const SEGMENTS = [
  { value: 'all', label: 'Tout', key: null },
  { value: '31_60', label: '31–60 j', key: 'b31_60' },
  { value: '61_90', label: '61–90 j', key: 'b61_90' },
  { value: '90_plus', label: '90+ j', key: 'b90_plus' },
]

export default function BalanceAgeePage() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  // ERR62 — distinguer « serveur indisponible » de « aucun encours » : un
  // échec de chargement affiche un état d'erreur + bouton Réessayer au lieu
  // d'un tableau vide trompeur.
  const [loadError, setLoadError] = useState(false)
  const [segment, setSegment] = useState('all')
  const [exporting, setExporting] = useState(false)
  const [exportError, setExportError] = useState('')

  const load = () => ventesApi.getBalanceAgee()
    .then(r => { setRows(r.data); setLoadError(false) })
    .catch(() => setLoadError(true))
    .finally(() => setLoading(false))

  useEffect(() => { load() }, [])

  const releve = async (r) => {
    try {
      const res = await ventesApi.getClientRelevePdf(r.client_id)
      openPdfBlob(res.data, `Releve_${r.client_nom}.pdf`)
    } catch { toast.error('Relevé indisponible.') }
  }

  // Export .xlsx (une ligne par client, buckets + total) — borné société.
  const exporter = async () => {
    setExportError('')
    setExporting(true)
    try {
      const res = await reportingApi.balanceAgeeXlsx()
      downloadXlsx(res.data, 'balance-agee.xlsx')
    } catch {
      setExportError('Export indisponible. Réessayez.')
    } finally {
      setExporting(false)
    }
  }

  const filtered = useMemo(() => {
    const seg = SEGMENTS.find(s => s.value === segment)
    if (!seg?.key) return rows
    return rows.filter(r => Number(r[seg.key] || 0) > 0)
  }, [rows, segment])

  const sum = (k) => filtered.reduce((s, r) => s + Number(r[k] || 0), 0)

  return (
    <div className="ui-root page">
      <div className="page-header" style={{ marginBottom: '1.25rem' }}>
        <h2>Balance âgée</h2>
        <div className="flex flex-wrap items-center gap-2">
          {!loading && rows.length > 0 && (
            <Segmented size="sm" value={segment} onChange={setSegment} options={SEGMENTS} />
          )}
          {!loading && rows.length > 0 && (
            <Button variant="outline" size="sm" onClick={exporter} disabled={exporting}>
              <Download /> {exporting ? 'Export…' : 'Exporter'}
            </Button>
          )}
        </div>
      </div>

      {exportError && (
        <div className="mb-3 rounded border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {exportError}
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
      ) : loadError ? (
        // VX67 — StateBlock unifie l'état d'erreur avec un bouton « Réessayer »
        // (relance le même `load` qu'au montage).
        <Card>
          <CardContent className="py-6">
            <StateBlock
              error="La balance âgée n'a pas pu être chargée (serveur indisponible ?)."
              onRetry={load}
            />
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="p-0 sm:p-0">
            {/* J146 — migré vers le primitif Table partagé (plus de data-table). */}
            <Table
              aria-label="Balance âgée"
              getRowKey={(r) => r.client_id}
              columns={[
                { key: 'client_nom', header: 'Client', cell: (r) => <strong>{r.client_nom}</strong> },
                { key: 'b0_30', header: '0–30 j', align: 'right', cell: (r) => dh(r.b0_30) },
                { key: 'b31_60', header: '31–60 j', align: 'right', cell: (r) => dh(r.b31_60) },
                { key: 'b61_90', header: '61–90 j', align: 'right', cell: (r) => dh(r.b61_90) },
                { key: 'b90_plus', header: '90+ j', align: 'right', cellClassName: 'text-destructive', cell: (r) => dh(r.b90_plus) },
                { key: 'total', header: 'Total dû', align: 'right', cell: (r) => <strong>{dh(r.total)}</strong> },
                {
                  key: 'releve',
                  header: '',
                  align: 'right',
                  cell: (r) => (
                    <div className="flex justify-end gap-2">
                      {/* VX112 — drill-down vers les relances filtrées sur ce
                          client (mirroir du pré-filtre ?produit= de
                          MouvementsPage) : la balance âgée n'est plus un
                          cul-de-sac, elle mène à l'action de recouvrement. */}
                      <Button variant="outline" size="sm" asChild>
                        <Link to={`/ventes/relances?client=${r.client_id}`}>
                          <Send /> Relancer
                        </Link>
                      </Button>
                      <Button variant="outline" size="sm" onClick={() => releve(r)}>
                        <FileText /> Relevé
                      </Button>
                    </div>
                  ),
                },
              ]}
              rows={filtered}
              empty={(
                <EmptyState
                  icon={CheckCircle2}
                  title="Aucun encours client"
                  description={segment === 'all'
                    ? 'Aucune facture impayée en attente de règlement.'
                    : 'Aucun encours dans cette tranche.'}
                  className="border-0 py-6"
                />
              )}
              footer={filtered.length > 0 && (
                <tr className="border-t border-border font-bold">
                  <td className="px-3 py-2" data-label="Total">Total</td>
                  <td className="px-3 py-2 text-right tabular-nums" data-label="0–30 j">{dh(sum('b0_30'))}</td>
                  <td className="px-3 py-2 text-right tabular-nums" data-label="31–60 j">{dh(sum('b31_60'))}</td>
                  <td className="px-3 py-2 text-right tabular-nums" data-label="61–90 j">{dh(sum('b61_90'))}</td>
                  <td className="px-3 py-2 text-right tabular-nums" data-label="90+ j">{dh(sum('b90_plus'))}</td>
                  <td className="px-3 py-2 text-right tabular-nums" data-label="Total dû">{dh(sum('total'))}</td>
                  <td className="px-3 py-2" />
                </tr>
              )}
            />
          </CardContent>
        </Card>
      )}
    </div>
  )
}
