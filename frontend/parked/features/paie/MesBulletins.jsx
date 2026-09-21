import { useEffect, useState } from 'react'
import { Download, Wallet } from 'lucide-react'
import { ListShell } from '../../ui/module'
import { toast } from '../../ui'
import { formatMAD } from '../../lib/format'
import { openPdfBlob } from '../../utils/pdfBlob'
import paieApi from '../../api/paieApi'

/* ============================================================================
   UX14 — Mes bulletins (self-service employé).
   ----------------------------------------------------------------------------
   Accessible à TOUT rôle : l'employé voit et télécharge UNIQUEMENT ses propres
   bulletins VALIDÉS. L'isolation est garantie côté serveur (get_queryset scopé
   à profil.employe.user) — le client ne fait qu'afficher ce qu'il reçoit.
   ========================================================================== */
export default function MesBulletins() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let alive = true
    paieApi.getMesBulletins({ ordering: '-periode' })
      .then((r) => alive && setRows(listOf(r.data)))
      .catch(() => alive && setError('Chargement de vos bulletins impossible.'))
      .finally(() => alive && setLoading(false))
    return () => { alive = false }
  }, [])

  const telecharger = async (row) => {
    try {
      const { data } = await paieApi.mesBulletinPdf(row.id)
      openPdfBlob(data, `bulletin_${row.id}.pdf`)
    } catch {
      toast.error('PDF indisponible pour le moment.')
    }
  }

  const columns = [
    { id: 'periode', header: 'Période', accessor: (r) => r.periode,
      cell: (_v, r) => `Période ${r.periode}` },
    { id: 'brut', header: 'Brut', align: 'right',
      accessor: (r) => Number(r.brut) || 0, cell: (_v, r) => formatMAD(r.brut) },
    { id: 'net', header: 'Net à payer', align: 'right',
      accessor: (r) => Number(r.net_a_payer) || 0,
      cell: (_v, r) => formatMAD(r.net_a_payer) },
  ]

  return (
    <ListShell
      title="Mes bulletins"
      subtitle="Consultez et téléchargez vos bulletins de paie validés."
      columns={columns}
      rows={rows}
      loading={loading}
      error={error}
      searchable={false}
      exportName="mes-bulletins"
      rowActions={(r) => [
        { id: 'pdf', label: 'Télécharger', icon: Download,
          onClick: () => telecharger(r) },
      ]}
      emptyTitle="Aucun bulletin"
      emptyDescription="Vos bulletins validés apparaîtront ici."
    >
      <div className="flex items-center gap-2 rounded-lg border border-border bg-muted/40 p-3 text-sm text-muted-foreground">
        <Wallet size={16} aria-hidden="true" />
        Seuls vos propres bulletins validés sont visibles ici.
      </div>
    </ListShell>
  )
}

function listOf(data) {
  return Array.isArray(data) ? data : (data?.results ?? [])
}
