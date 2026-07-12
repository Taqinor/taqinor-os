/* Pièces jointes (style Odoo) pour n'importe quel enregistrement.
   Réutilisable : model ('crm.lead'…) + id. Ajout = Commerciale ; suppression
   = admin (le backend l'impose ; on masque le bouton pour les autres).

   G26 — reconstruit sur le primitif FileUpload (dropzone + validation). Les
   appels réseau sont STRICTEMENT préservés : recordsApi.getAttachments /
   uploadAttachment / deleteAttachment. Le téléchargement passe TOUJOURS par
   `a.url` (= le proxy Django /records/attachments/<id>/download/ renvoyé par le
   sérialiseur) — jamais une URL MinIO brute. */
import { useEffect, useState } from 'react'
import { useIsAdmin } from '../hooks/useHasPermission'
import { Paperclip, FileText, ImageOff, Trash2 } from 'lucide-react'
import recordsApi from '../api/recordsApi'
import api from '../api/axios'
import { FileUpload } from '../ui/FileUpload'
import { formatFileSize, compressImage } from '../ui/file-utils'
import { formatDate } from '../lib/format'

const ACCEPT = 'application/pdf,image/png,image/jpeg,image/webp'
const MAX_SIZE = 10 * 1024 * 1024 // 10 Mo
// L867 — contraintes affichées AVANT tout upload (en plus de la validation
// client-side du dropzone), pour qu'on les connaisse sans déclencher un rejet.
const CONSTRAINTS = 'PDF/PNG/JPEG/WebP — 10 Mo max'

const isImage = (mime) => typeof mime === 'string' && mime.startsWith('image/')

export default function AttachmentsPanel({ model, id, onChange }) {
  const isAdmin = useIsAdmin()
  const [items, setItems] = useState([])
  const [busy, setBusy] = useState(false)
  const [progress, setProgress] = useState(undefined)
  const [error, setError] = useState(null)
  // L866 — pièces dont l'aperçu image a échoué (objet MinIO supprimé/404).
  const [brokenThumbs, setBrokenThumbs] = useState({})

  const load = () => {
    recordsApi.getAttachments(model, id)
      .then((r) => setItems(r.data.results ?? r.data)).catch(() => {})
  }
  useEffect(() => { load() }, [model, id]) // eslint-disable-line react-hooks/exhaustive-deps

  const upload = async (file) => {
    if (!file) return
    setBusy(true); setError(null); setProgress(0)
    try {
      // VX246(a) — les images (photo terrain, capture d'écran) sont compressées
      // avant l'envoi ; compressImage renvoie les PDF/non-images intacts, donc
      // la pièce PDF passe telle quelle.
      const toSend = await compressImage(file)
      // L868 — progression d'upload : même endpoint que recordsApi
      // (/records/attachments/, MÊME ORIGINE, cookie d'auth) avec
      // onUploadProgress pour piloter la barre du dropzone sur les gros
      // fichiers.
      const fd = new FormData()
      fd.append('model', model)
      fd.append('id', id)
      fd.append('file', toSend)
      await api.post('/records/attachments/', fd, {
        onUploadProgress: (e) => {
          if (e.total) setProgress(Math.round((e.loaded / e.total) * 100))
        },
      })
      load(); onChange?.()
    } catch (err) {
      setError(err.response?.data?.detail ?? "Échec de l'envoi.")
    } finally { setBusy(false); setProgress(undefined) }
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
        progress={progress}
        hint={CONSTRAINTS}
        onFiles={(files) => upload(files[0])}
        onReject={(rejected) => setError(rejected[0]?.error ?? 'Fichier refusé.')}
      />

      {/* L867 — contraintes rappelées sous le dropzone (toujours visibles). */}
      <p className="text-xs text-muted-foreground">{CONSTRAINTS}</p>

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
              className="att-name flex min-w-0 flex-1 items-center gap-2 font-medium text-foreground hover:text-primary hover:underline"
            >
              {/* L866 — vignette pour les images ; si le fetch 404 (objet MinIO
                  supprimé), on remplace le glyphe cassé par une tuile FR. */}
              {isImage(a.mime) && !brokenThumbs[a.id] ? (
                <img
                  src={a.url}
                  alt=""
                  className="size-8 shrink-0 rounded object-cover"
                  loading="lazy"
                  onError={() =>
                    setBrokenThumbs((b) => ({ ...b, [a.id]: true }))}
                />
              ) : isImage(a.mime) ? (
                <span
                  className="grid size-8 shrink-0 place-items-center rounded bg-muted text-[10px] text-muted-foreground"
                  title="Aperçu indisponible"
                >
                  <ImageOff className="size-4" aria-hidden="true" />
                </span>
              ) : (
                <FileText className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
              )}
              <span className="truncate">
                {a.filename}
                {isImage(a.mime) && brokenThumbs[a.id] && (
                  <span className="ml-1 text-xs text-muted-foreground">
                    (Aperçu indisponible)
                  </span>
                )}
              </span>
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
