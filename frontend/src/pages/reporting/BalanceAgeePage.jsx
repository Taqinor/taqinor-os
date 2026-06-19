import { useEffect, useMemo, useState } from 'react'
import { FileText, CheckCircle2, Download } from 'lucide-react'
import ventesApi from '../../api/ventesApi'
import reportingApi from '../../api/reportingApi'
import { downloadXlsx } from '../../api/importApi'
import { openPdfBlob } from '../../utils/pdfBlob'
import { formatMAD } from '../../lib/format'
import { Button, Card, CardContent, Segmented, Skeleton, EmptyState } from '../../ui'

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
  const [segment, setSegment] = useState('all')
  const [exporting, setExporting] = useState(false)
  const [exportError, setExportError] = useState('')

  useEffect(() => {
    ventesApi.getBalanceAgee()
      .then(r => setRows(r.data)).catch(() => {}).finally(() => setLoading(false))
  }, [])

  const releve = async (r) => {
    try {
      const res = await ventesApi.getClientRelevePdf(r.client_id)
      openPdfBlob(res.data, `Releve_${r.client_nom}.pdf`)
    } catch { alert('Relevé indisponible.') }
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
      ) : (
        <Card>
          <CardContent className="overflow-x-auto p-0 sm:p-0">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Client</th>
                  <th className="ta-right">0–30 j</th>
                  <th className="ta-right">31–60 j</th>
                  <th className="ta-right">61–90 j</th>
                  <th className="ta-right">90+ j</th>
                  <th className="ta-right">Total dû</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {filtered.map(r => (
                  <tr key={r.client_id}>
                    <td data-label="Client"><strong>{r.client_nom}</strong></td>
                    <td data-label="0–30 j" className="ta-right tabular-nums">{dh(r.b0_30)}</td>
                    <td data-label="31–60 j" className="ta-right tabular-nums">{dh(r.b31_60)}</td>
                    <td data-label="61–90 j" className="ta-right tabular-nums">{dh(r.b61_90)}</td>
                    <td data-label="90+ j" className="ta-right tabular-nums text-destructive">{dh(r.b90_plus)}</td>
                    <td data-label="Total dû" className="ta-right tabular-nums"><strong>{dh(r.total)}</strong></td>
                    <td className="ta-right">
                      <Button variant="outline" size="sm" onClick={() => releve(r)}>
                        <FileText /> Relevé
                      </Button>
                    </td>
                  </tr>
                ))}
                {filtered.length === 0 && (
                  <tr>
                    <td colSpan={7}>
                      <EmptyState
                        icon={CheckCircle2}
                        title="Aucun encours client"
                        description={segment === 'all'
                          ? 'Aucune facture impayée en attente de règlement.'
                          : 'Aucun encours dans cette tranche.'}
                        className="border-0 py-6"
                      />
                    </td>
                  </tr>
                )}
              </tbody>
              {filtered.length > 0 && (
                <tfoot>
                  <tr className="font-bold">
                    <td data-label="Total">Total</td>
                    <td data-label="0–30 j" className="ta-right tabular-nums">{dh(sum('b0_30'))}</td>
                    <td data-label="31–60 j" className="ta-right tabular-nums">{dh(sum('b31_60'))}</td>
                    <td data-label="61–90 j" className="ta-right tabular-nums">{dh(sum('b61_90'))}</td>
                    <td data-label="90+ j" className="ta-right tabular-nums">{dh(sum('b90_plus'))}</td>
                    <td data-label="Total dû" className="ta-right tabular-nums">{dh(sum('total'))}</td>
                    <td></td>
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
