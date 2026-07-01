import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { FileText, Download } from 'lucide-react'
import { ListShell } from '../../ui/module'
import { toast } from '../../ui'
import { formatMAD } from '../../lib/format'
import { openPdfBlob } from '../../utils/pdfBlob'
import paieApi from '../../api/paieApi'
import { StatutBulletin } from './statuses.jsx'

/* UX11 — Liste des bulletins de paie (aperçu, drill-in vers le détail). */
export default function BulletinList() {
  const navigate = useNavigate()
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let alive = true
    paieApi.getBulletins()
      .then((r) => alive && setRows(listOf(r.data)))
      .catch(() => alive && setError('Chargement des bulletins impossible.'))
      .finally(() => alive && setLoading(false))
    return () => { alive = false }
  }, [])

  const telecharger = async (row) => {
    try {
      const { data } = await paieApi.bulletinPdf(row.id)
      openPdfBlob(data, `bulletin_${row.id}.pdf`)
    } catch {
      toast.error('PDF indisponible (moteur de rendu).')
    }
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
      rowActions={(r) => [
        { label: 'Ouvrir', icon: FileText,
          onClick: () => navigate(`/paie/bulletins/${r.id}`) },
        { label: 'Télécharger PDF', icon: Download,
          onClick: () => telecharger(r) },
      ]}
      emptyTitle="Aucun bulletin"
      emptyDescription="Générez des bulletins depuis le run de paie."
    />
  )
}

function listOf(data) {
  return Array.isArray(data) ? data : (data?.results ?? [])
}
