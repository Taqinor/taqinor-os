import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { FileText, Download, XCircle, Printer } from 'lucide-react'
import { ListShell } from '../../ui/module'
import {
  toast, Button, Select, SelectTrigger, SelectValue, SelectContent,
  SelectItem,
} from '../../ui'
import { formatMAD } from '../../lib/format'
import { openPdfBlob } from '../../utils/pdfBlob'
import paieApi from '../../api/paieApi'
import { StatutBulletin } from './statuses.jsx'
import { BULLETIN_STATUTS } from './paieLogic.js'

/* UX11 — Liste des bulletins de paie (aperçu, drill-in vers le détail). */
export default function BulletinList() {
  const navigate = useNavigate()
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [periodes, setPeriodes] = useState([])
  const [periodeImpression, setPeriodeImpression] = useState('')
  const [busy, setBusy] = useState('')

  const load = () => {
    let alive = true
    paieApi.getBulletins()
      .then((r) => alive && setRows(listOf(r.data)))
      .catch(() => alive && setError('Chargement des bulletins impossible.'))
      .finally(() => alive && setLoading(false))
    return () => { alive = false }
  }
  useEffect(() => load(), []) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    paieApi.getPeriodes().then((r) => setPeriodes(listOf(r.data))).catch(() => {})
  }, [])

  const telecharger = async (row) => {
    try {
      const { data } = await paieApi.bulletinPdf(row.id)
      openPdfBlob(data, `bulletin_${row.id}.pdf`)
    } catch {
      toast.error('PDF indisponible (moteur de rendu).')
    }
  }

  // ZPAI4 — annule un bulletin (crée un bulletin d'annulation, à montant
  // opposé, sans jamais toucher au bulletin d'origine).
  const annuler = async (row) => {
    if (!row.periode) return
    setBusy(`annuler-${row.id}`)
    try {
      await paieApi.annulerBulletin(row.id, { periode_cible: row.periode })
      toast.success('Bulletin d’annulation créé.')
      load()
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Annulation impossible.')
    } finally { setBusy('') }
  }

  // ZPAI5 — impression en lot des bulletins VALIDÉS d'une période.
  const imprimerLot = async () => {
    if (!periodeImpression) { toast.error('Choisissez une période.'); return }
    setBusy('lot')
    try {
      const { data } = await paieApi.bulletinsPdf(periodeImpression)
      openPdfBlob(data, `bulletins_periode_${periodeImpression}.pdf`)
    } catch {
      toast.error('Impression en lot indisponible.')
    } finally { setBusy('') }
  }

  const columns = [
    { id: 'id', header: 'N°', width: 70, accessor: (r) => r.id,
      cell: (_v, r) => `#${r.id}` },
    { id: 'periode', header: 'Période', accessor: (r) => r.periode,
      cell: (_v, r) => `Période ${r.periode}` },
    { id: 'profil', header: 'Profil', accessor: (r) => r.profil,
      cell: (_v, r) => `Profil #${r.profil}` },
    { id: 'brut', header: 'Brut', align: 'right',
      accessor: (r) => Number(r.brut) || 0, cell: (_v, r) => formatMAD(r.brut) },
    { id: 'net', header: 'Net à payer', align: 'right',
      accessor: (r) => Number(r.net_a_payer) || 0,
      cell: (_v, r) => formatMAD(r.net_a_payer) },
    { id: 'statut', header: 'Statut', accessor: (r) => r.statut,
      cell: (_v, r) => <StatutBulletin status={r.statut} /> },
  ]

  return (
    <ListShell
      title="Bulletins de paie"
      subtitle="Aperçu, détail du calcul et téléchargement PDF."
      columns={columns}
      rows={rows}
      loading={loading}
      error={error}
      searchable
      exportName="bulletins-paie"
      onRowClick={(r) => navigate(`/paie/bulletins/${r.id}`)}
      actions={
        <div className="flex flex-wrap items-center gap-2">
          <Select value={periodeImpression} onValueChange={setPeriodeImpression}>
            <SelectTrigger className="w-48"><SelectValue placeholder="Période…" /></SelectTrigger>
            <SelectContent>
              {periodes.map((p) => (
                <SelectItem key={p.id} value={String(p.id)}>
                  {p.libelle || `${p.mois}/${p.annee}`}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button variant="outline" onClick={imprimerLot} loading={busy === 'lot'}>
            <Printer size={16} aria-hidden="true" /> Imprimer (lot)
          </Button>
        </div>
      }
      rowActions={(r) => [
        { label: 'Ouvrir', icon: FileText,
          onClick: () => navigate(`/paie/bulletins/${r.id}`) },
        { label: 'Télécharger PDF', icon: Download,
          onClick: () => telecharger(r) },
        ...(r.statut === BULLETIN_STATUTS.VALIDE ? [{
          label: 'Annuler (contre-passation)', icon: XCircle,
          onClick: () => annuler(r),
        }] : []),
      ]}
      emptyTitle="Aucun bulletin"
      emptyDescription="Générez des bulletins depuis le run de paie."
    />
  )
}

function listOf(data) {
  return Array.isArray(data) ? data : (data?.results ?? [])
}
