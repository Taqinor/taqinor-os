import { useEffect, useState, lazy, Suspense } from 'react'
import {
  FileText, FolderOpen, AlertTriangle, Download, Eye, X,
} from 'lucide-react'
import api from '../../api/axios'
import reportingApi from '../../api/reportingApi'
import { Button, Card, CardHeader, CardTitle, CardContent, Badge, Skeleton, EmptyState } from '../../ui'
import { Table } from './Table'
import { typeLabel, sortDocsDesc } from './archiveDocs'

// L865 — on réutilise le renderer PDF.js (canvas, même origine) du panneau
// devis pour prévisualiser les documents d'archive INLINE, avec repli
// téléchargement. Chargé en lazy : le worker PDF.js ne pèse que si on ouvre un
// aperçu.
const PdfCanvas = lazy(() => import('../../features/ventes/PdfCanvas'))

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
  // L860 — erreur par ligne (clé = index) au lieu d'un pop-up bloquant.
  const [rowError, setRowError] = useState({})
  const [exporting, setExporting] = useState(false)
  // L865 — aperçu PDF inline : { reference, blob } | { reference, failed }.
  const [preview, setPreview] = useState(null)
  const [previewLoading, setPreviewLoading] = useState(false)

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

  // L860 + L865 — ouvre le document dans l'aperçu PDF.js inline ; en cas
  // d'échec serveur, on affiche un message inline dans la ligne (jamais alert).
  const openDoc = async (doc, i) => {
    setRowError((e) => ({ ...e, [i]: null }))
    if (!doc.download_url) {
      setRowError((e) => ({ ...e, [i]: 'Ce document n’a pas de PDF.' }))
      return
    }
    setPreviewLoading(true)
    setPreview({ reference: doc.reference || typeLabel(doc) })
    try {
      // download_url commence par /api/ ; l'intercepteur axios ne le préfixe
      // pas. Cookies httpOnly envoyés.
      const r = await api.get(doc.download_url, { responseType: 'blob' })
      setPreview({ reference: doc.reference || typeLabel(doc), blob: r.data, url: doc.download_url })
    } catch {
      setRowError((e) => ({ ...e, [i]: 'Document indisponible.' }))
      setPreview(null)
    } finally {
      setPreviewLoading(false)
    }
  }

  // Repli téléchargement depuis l'aperçu (ou si le canvas échoue à rendre).
  const downloadPreview = () => {
    if (!preview?.blob) return
    const objectUrl = URL.createObjectURL(preview.blob)
    const a = document.createElement('a')
    a.href = objectUrl
    a.download = `${preview.reference || 'document'}.pdf`
    document.body.appendChild(a)
    a.click()
    a.remove()
    setTimeout(() => URL.revokeObjectURL(objectUrl), 60000)
  }

  // L864 — « Tout exporter (.xlsx) » : la liste filtrée (type/référence/date),
  // scopée société côté serveur, jamais de prix d'achat.
  const exportXlsx = async () => {
    setExporting(true)
    setError(null)
    try {
      const path = kind === 'chantier'
        ? `/reporting/archive/chantier/${id}/`
        : `/reporting/archive/client/${id}/`
      const r = await api.get(path, {
        params: { export: 'xlsx' }, responseType: 'blob',
      })
      const objectUrl = URL.createObjectURL(r.data)
      const a = document.createElement('a')
      a.href = objectUrl
      a.download = `archive-${kind}-${id}.xlsx`
      document.body.appendChild(a)
      a.click()
      a.remove()
      setTimeout(() => URL.revokeObjectURL(objectUrl), 60000)
    } catch {
      setError("L’export n’a pas pu être généré.")
    } finally {
      setExporting(false)
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

  if (error && !data) {
    return <EmptyState icon={AlertTriangle} title="Archive indisponible" description={error} />
  }
  if (!data) return null

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between gap-2">
        <CardTitle>Documents</CardTitle>
        <div className="flex items-center gap-2">
          <Badge tone="neutral">{data.count}</Badge>
          {data.documents.length > 0 && (
            <Button variant="outline" size="sm" onClick={exportXlsx}
                    loading={exporting} disabled={exporting}>
              {!exporting && <Download />}
              {exporting ? 'Export…' : 'Tout exporter (.xlsx)'}
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {/* L860 — échec d'export montré inline (jamais alert). */}
        {error && (
          <div className="form-error-box" role="alert" style={{ marginBottom: 12 }}>
            {error}
          </div>
        )}
        {data.documents.length === 0 ? (
          <EmptyState
            icon={FolderOpen}
            title="Aucun document"
            description="Aucun document n’a encore été généré pour cette fiche."
            className="border-0 py-6"
          />
        ) : (
          /* J146 — migré vers le primitif Table partagé (plus de data-table). */
          <Table
            aria-label="Documents archivés"
            columns={[
              { key: 'type', header: 'Type', cell: (d) => typeLabel(d) },
              { key: 'reference', header: 'Référence', cell: (d) => d.reference || '—' },
              { key: 'date', header: 'Date', cellClassName: 'tabular-nums', cell: (d) => d.date || '—' },
              {
                key: 'action',
                header: '',
                align: 'right',
                cell: (d, i) => ((d.has_pdf ?? !!d.download_url) ? (
                  <div className="flex flex-col items-end gap-1">
                    <Button variant="outline" size="sm" onClick={() => openDoc(d, i)}>
                      <Eye /> Aperçu
                    </Button>
                    {/* L860 — erreur de fetch PDF montrée inline. */}
                    {rowError[i] && (
                      <span className="text-xs text-destructive" role="alert">
                        {rowError[i]}
                      </span>
                    )}
                  </div>
                ) : (
                  // L863 — bon de commande sans PDF : affordance claire.
                  <span className="text-xs text-muted-foreground">Pas de PDF</span>
                )),
              },
            ]}
            rows={sortDocsDesc(data.documents)}
          />
        )}
      </CardContent>

      {/* L865 — aperçu PDF.js inline, même origine, avec repli téléchargement. */}
      {preview && (
        <div
          className="fixed inset-0 z-[var(--z-overlay)] flex items-center justify-center bg-black/50 p-4"
          role="dialog"
          aria-modal="true"
          onClick={() => setPreview(null)}
        >
          <div
            className="flex max-h-[90vh] w-full max-w-3xl flex-col overflow-hidden rounded-lg bg-card"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between gap-2 border-b border-border px-4 py-2">
              <span className="truncate text-sm font-medium">{preview.reference}</span>
              <div className="flex items-center gap-2">
                {preview.blob && (
                  <Button variant="outline" size="sm" onClick={downloadPreview}>
                    <Download /> Télécharger
                  </Button>
                )}
                <button
                  type="button"
                  aria-label="Fermer l’aperçu"
                  onClick={() => setPreview(null)}
                  className="grid size-8 place-items-center rounded-md text-muted-foreground hover:bg-muted"
                >
                  <X className="size-4" />
                </button>
              </div>
            </div>
            <div className="ldp-pdf-area overflow-auto p-3">
              {previewLoading && (
                <p className="ldp-pdf-loading">⏳ Chargement de l’aperçu…</p>
              )}
              {preview.failed && (
                <EmptyState
                  role="alert"
                  icon={AlertTriangle}
                  title="Aperçu indisponible"
                  description="Le document n’a pas pu s’afficher."
                  action={preview.blob ? (
                    <Button size="sm" onClick={downloadPreview}>
                      <FileText /> Télécharger le PDF
                    </Button>
                  ) : null}
                />
              )}
              {preview.blob && !preview.failed && (
                <Suspense fallback={<p className="ldp-pdf-loading">⏳ Rendu de l’aperçu…</p>}>
                  <PdfCanvas
                    blob={preview.blob}
                    onError={() => setPreview((p) => ({ ...p, failed: true }))}
                  />
                </Suspense>
              )}
            </div>
          </div>
        </div>
      )}
    </Card>
  )
}
