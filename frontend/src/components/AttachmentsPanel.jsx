/* Pièces jointes (style Odoo) pour n'importe quel enregistrement.
   Réutilisable : model ('crm.lead'…) + id. Ajout = Commerciale ; suppression
   = admin (le backend l'impose ; on masque le bouton pour les autres).

   G26 — reconstruit sur le primitif FileUpload (dropzone + validation). Les
   appels réseau sont STRICTEMENT préservés : recordsApi.getAttachments /
   uploadAttachment / deleteAttachment. Le téléchargement passe TOUJOURS par
   `a.url` (= le proxy Django /records/attachments/<id>/download/ renvoyé par le
   sérialiseur) — jamais une URL MinIO brute. */
import { useEffect, useState } from 'react'
import { useSelector } from 'react-redux'
import { Paperclip, FileText, Trash2 } from 'lucide-react'
import recordsApi from '../api/recordsApi'
import { FileUpload } from '../ui/FileUpload'
import { formatFileSize } from '../ui/file-utils'
import { formatDate } from '../lib/format'

const ACCEPT = 'application/pdf,image/png,image/jpeg,image/webp'
const MAX_SIZE = 10 * 1024 * 1024 // 10 Mo

export default function AttachmentsPanel({ model, id, onChange }) {
  const role = useSelector((s) => s.auth.role)
  const isAdmin = role === 'admin'
  const [items, setItems] = useState([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  const load = () => {
    recordsApi.getAttachments(model, id)
      .then((r) => setItems(r.data.results ?? r.data)).catch(() => {})
  }
  useEffect(() => { load() }, [model, id]) // eslint-disable-line react-hooks/exhaustive-deps

  const upload = async (file) => {
    if (!file) return
    setBusy(true); setError(null)
    try {
      await recordsApi.uploadAttachment(model, id, file)
      load(); onChange?.()
    } catch (err) {
      setError(err.response?.data?.detail ?? "Échec de l'envoi.")
    } finally { setBusy(false) }
  }

  const remove = async (att) => {
    if (!window.confirm('Supprimer cette pièce jointe ?')) return
    try { await recordsApi.deleteAttachment(att.id); load(); onChange?.() } catch { /* */ }
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2 text-sm font-medium text-foreground">
        <Paperclip className="size-4 text-muted-foreground" aria-hidden="true" />
        {items.length} pièce(s) jointe(s)
      </div>

      <FileUpload
        accept={ACCEPT}
        maxSize={MAX_SIZE}
        busy={busy}
        disabled={busy}
        onFiles={(files) => upload(files[0])}
        onReject={(rejected) => setError(rejected[0]?.error ?? 'Fichier refusé.')}
      />

      {error && (
        <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive" role="alert">
          {error}
        </div>
      )}

      <div className="flex flex-col gap-1.5">
        {items.length === 0 && (
          <p className="text-sm text-muted-foreground">Aucune pièce jointe.</p>
        )}
        {items.map((a) => (
          <div key={a.id} className="flex items-center gap-2 rounded-md border border-border bg-card px-3 py-2 text-sm">
            {/* Téléchargement via le proxy Django (a.url) — jamais MinIO direct. */}
            <a
              href={a.url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex min-w-0 flex-1 items-center gap-2 font-medium text-foreground hover:text-primary hover:underline"
            >
              <FileText className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
              <span className="truncate">{a.filename}</span>
            </a>
            <span className="shrink-0 text-xs text-muted-foreground">
              {formatFileSize(a.size)}
              {a.uploaded_by_nom ? ` · ${a.uploaded_by_nom}` : ''}
              {a.created_at ? ` · ${formatDate(a.created_at)}` : ''}
            </span>
            {isAdmin && (
              <button
                type="button"
                title="Supprimer"
                aria-label={`Supprimer ${a.filename}`}
                onClick={() => remove(a)}
                className="grid size-7 shrink-0 place-items-center rounded-md text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <Trash2 className="size-4" />
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
