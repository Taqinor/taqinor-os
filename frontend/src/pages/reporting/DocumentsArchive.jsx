import { useEffect, useState } from 'react'
import { FileText, FolderOpen, AlertTriangle } from 'lucide-react'
import api from '../../api/axios'
import reportingApi from '../../api/reportingApi'
import { Button, Card, CardHeader, CardTitle, CardContent, Badge, Skeleton, EmptyState } from '../../ui'
import { typeLabel, sortDocsDesc } from './archiveDocs'

// N32 — Archive documentaire (par client ou par chantier). Composant
// réutilisable : agrège tous les documents générés (devis, factures, avoirs,
// bons de commande + documents post-vente) et pointe vers les endpoints de
// téléchargement EXISTANTS, qui régénèrent le PDF à la demande. Lecture seule.
//
// Props :
//   - kind : 'client' | 'chantier'
//   - id   : identifiant du client ou du chantier
//
// Utilisable comme page (via les wrappers ArchiveClientPage / ArchiveChantierPage)
// ou intégrable en panneau dans la fiche client / chantier.
export default function DocumentsArchive({ kind, id }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let alive = true
    const run = async () => {
      await Promise.resolve()
      if (!alive) return
      setLoading(true)
      setError(null)
      try {
        const r = kind === 'chantier'
          ? await reportingApi.getArchiveChantier(id)
          : await reportingApi.getArchiveClient(id)
        if (alive) setData(r.data)
      } catch {
        if (alive) setError('Archive indisponible.')
      }
      if (alive) setLoading(false)
    }
    if (id != null) run()
    return () => { alive = false }
  }, [kind, id])

  const openDoc = async (doc) => {
    if (!doc.download_url) {
      alert('Ce document n’a pas de PDF téléchargeable.')
      return
    }
    try {
      // download_url est un chemin /api/django/... ; l'intercepteur axios ne le
      // préfixe pas (il commence déjà par /api/). Cookies httpOnly envoyés.
      const r = await api.get(doc.download_url, { responseType: 'blob' })
      const url = URL.createObjectURL(r.data)
      window.open(url, '_blank')
      setTimeout(() => URL.revokeObjectURL(url), 60000)
    } catch {
      alert('Document indisponible.')
    }
  }

  if (loading) {
    return (
      <Card>
        <CardHeader><Skeleton className="h-4 w-40" /></CardHeader>
        <CardContent className="space-y-2">
          {Array.from({ length: 4 }).map((unused, i) => (
            <Skeleton key={i} className="h-9 w-full" />
          ))}
        </CardContent>
      </Card>
    )
  }

  if (error) {
    return <EmptyState icon={AlertTriangle} title="Archive indisponible" description={error} />
  }
  if (!data) return null

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between gap-2">
        <CardTitle>Documents</CardTitle>
        <Badge tone="neutral">{data.count}</Badge>
      </CardHeader>
      <CardContent>
        {data.documents.length === 0 ? (
          <EmptyState
            icon={FolderOpen}
            title="Aucun document"
            description="Aucun document n’a encore été généré pour cette fiche."
            className="border-0 py-6"
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr><th>Type</th><th>Référence</th><th>Date</th><th /></tr>
              </thead>
              <tbody>
                {sortDocsDesc(data.documents).map((d, i) => (
                  <tr key={i}>
                    <td data-label="Type">{typeLabel(d)}</td>
                    <td data-label="Référence">{d.reference || '—'}</td>
                    <td data-label="Date" className="tabular-nums">{d.date || '—'}</td>
                    <td className="ta-right">
                      {d.download_url ? (
                        <Button variant="outline" size="sm" onClick={() => openDoc(d)}>
                          <FileText /> Ouvrir le PDF
                        </Button>
                      ) : (
                        <span className="text-xs text-muted-foreground">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
