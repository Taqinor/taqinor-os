import { useEffect, useState } from 'react'
import { useSelector } from 'react-redux'
import { FileX2, FileText } from 'lucide-react'
import ventesApi from '../../api/ventesApi'
import { openPdfBlob } from '../../utils/pdfBlob'
import {
  Button, Badge, StatusPill, Card, EmptyState, Spinner,
  AlertDialog, AlertDialogTrigger, AlertDialogContent, AlertDialogHeader,
  AlertDialogTitle, AlertDialogDescription, AlertDialogFooter,
  AlertDialogCancel, AlertDialogAction,
} from '../../ui'
import { formatMAD } from '../../lib/format'

export default function AvoirsPage() {
  const role = useSelector(s => s.auth.role)
  const isAdmin = role === 'admin'
  const [avoirs, setAvoirs] = useState([])
  const [loading, setLoading] = useState(true)

  const load = () => {
    setLoading(true)
    ventesApi.getAvoirs()
      .then(r => setAvoirs(r.data.results ?? r.data)).catch(() => {})
      .finally(() => setLoading(false))
  }
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { load() }, [])

  const download = async (a) => {
    try {
      const res = await ventesApi.telechargerAvoirPdf(a.id)
      openPdfBlob(res.data, `${a.reference}.pdf`)
    } catch { alert('PDF indisponible.') }
  }
  const annuler = async (a) => {
    try { await ventesApi.annulerAvoir(a.id); load() } catch { /* */ }
  }

  return (
    <div className="page">
      <div className="page-header">
        <h2>
          Avoirs (notes de crédit)
          {avoirs.length > 0 && <Badge tone="primary" className="ml-2 align-middle">{avoirs.length}</Badge>}
        </h2>
      </div>

      {loading ? (
        <div className="flex items-center justify-center gap-2 py-12 text-sm text-muted-foreground">
          <Spinner /> Chargement…
        </div>
      ) : avoirs.length === 0 ? (
        <EmptyState
          icon={FileX2}
          title="Aucun avoir"
          description="Créez-en un depuis une facture émise (bouton « Avoir » de la liste des factures)."
          className="mt-4"
        />
      ) : (
        <Card className="mt-4 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Référence</th><th>Facture</th><th>Client</th>
                  <th className="ta-right">Total TTC</th><th>Motif</th>
                  <th>Statut</th><th></th>
                </tr>
              </thead>
              <tbody>
                {avoirs.map(a => (
                  <tr key={a.id}>
                    <td><strong>{a.reference}</strong></td>
                    <td>{a.facture_reference}</td>
                    <td>{a.client_nom}</td>
                    <td className="ta-right tabular-nums">{formatMAD(a.total_ttc)}</td>
                    <td>{a.motif || '—'}</td>
                    <td>
                      <StatusPill status={a.statut} label={a.statut_display} />
                    </td>
                    <td className="ta-right">
                      <div className="flex items-center justify-end gap-2">
                        <Button size="sm" variant="outline" onClick={() => download(a)}>
                          <FileText /> PDF
                        </Button>
                        {isAdmin && a.statut !== 'annulee' && (
                          <AlertDialog>
                            <AlertDialogTrigger asChild>
                              <Button size="sm" variant="outline" className="border-destructive/40 text-destructive hover:bg-destructive/10">
                                Annuler
                              </Button>
                            </AlertDialogTrigger>
                            <AlertDialogContent>
                              <AlertDialogHeader>
                                <AlertDialogTitle>Annuler l'avoir {a.reference} ?</AlertDialogTitle>
                                <AlertDialogDescription>
                                  Cette action marque l'avoir comme annulé.
                                </AlertDialogDescription>
                              </AlertDialogHeader>
                              <AlertDialogFooter>
                                <AlertDialogCancel>Retour</AlertDialogCancel>
                                <AlertDialogAction onClick={() => annuler(a)}>Annuler l'avoir</AlertDialogAction>
                              </AlertDialogFooter>
                            </AlertDialogContent>
                          </AlertDialog>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  )
}
