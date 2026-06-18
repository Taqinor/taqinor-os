// N5 — Photos & fichiers du chantier, groupés avant / pendant / après, avec
// une galerie simple par phase. Réutilise les pièces jointes génériques
// (apps.records, cible installations.installation).
// J43 — porté sur le système de design (Button, IconButton, AlertDialog).
import { useEffect, useRef, useState } from 'react'
import { useSelector } from 'react-redux'
import { Plus, X, FileText } from 'lucide-react'
import recordsApi from '../../api/recordsApi'
import {
  Button,
  IconButton,
  AlertDialog,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogCancel,
  AlertDialogAction,
} from '../../ui'

const PHASES = [
  { key: 'avant', label: 'Avant' },
  { key: 'pendant', label: 'Pendant' },
  { key: 'apres', label: 'Après' },
]

const isImage = (a) => (a.mime ?? '').startsWith('image/')

export default function ChantierPhotos({ installationId }) {
  const isAdmin = useSelector((s) => s.auth.role) === 'admin'
  const [items, setItems] = useState([])
  const [busyPhase, setBusyPhase] = useState(null)
  const [toDelete, setToDelete] = useState(null)
  const fileRefs = { avant: useRef(null), pendant: useRef(null), apres: useRef(null) }

  const load = () => {
    recordsApi.getAttachments('installations.installation', installationId)
      .then((r) => setItems(r.data.results ?? r.data ?? [])).catch(() => {})
  }
  useEffect(() => { load() }, [installationId]) // eslint-disable-line react-hooks/exhaustive-deps

  const upload = async (phase, file) => {
    if (!file) return
    setBusyPhase(phase)
    try {
      await recordsApi.uploadAttachment('installations.installation', installationId, file, phase)
      load()
    } catch { /* erreur silencieuse */ } finally { setBusyPhase(null) }
  }

  const remove = async () => {
    if (!toDelete) return
    try { await recordsApi.deleteAttachment(toDelete.id); load() } catch { /* */ }
    setToDelete(null)
  }

  // Les pièces sans phase (anciennes / génériques) tombent dans « avant » par défaut.
  const byPhase = (key) => items.filter((a) => (a.phase || 'avant') === key)

  return (
    <div className="flex flex-wrap gap-4">
      {PHASES.map((p) => {
        const atts = byPhase(p.key)
        return (
          <div key={p.key} className="min-w-[220px] flex-1">
            <div className="mb-1.5 flex items-center justify-between">
              <strong className="text-sm text-foreground">{p.label} ({atts.length})</strong>
              <input ref={fileRefs[p.key]} type="file" className="sr-only"
                     accept="application/pdf,image/png,image/jpeg,image/webp"
                     onChange={(e) => { upload(p.key, e.target.files?.[0]); e.target.value = '' }} />
              <Button type="button" size="sm" variant="outline"
                      loading={busyPhase === p.key}
                      onClick={() => fileRefs[p.key].current?.click()}>
                {busyPhase === p.key ? null : <Plus />}
                Ajouter
              </Button>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {atts.length === 0 && (
                <span className="text-xs text-muted-foreground">Aucun fichier.</span>
              )}
              {atts.map((a) => (
                <div key={a.id} className="relative">
                  <a href={a.url} target="_blank" rel="noopener noreferrer" title={a.filename}>
                    {isImage(a) ? (
                      <img src={a.url} alt={a.filename}
                           className="size-16 rounded-md border border-border object-cover" />
                    ) : (
                      <span className="flex size-16 items-center justify-center rounded-md border border-border bg-muted text-muted-foreground">
                        <FileText className="size-6" aria-hidden="true" />
                      </span>
                    )}
                  </a>
                  {isAdmin && (
                    <IconButton
                      label="Supprimer"
                      variant="destructive"
                      onClick={() => setToDelete(a)}
                      className="absolute -right-1.5 -top-1.5 size-5 rounded-full p-0 [&_svg]:size-3"
                    >
                      <X />
                    </IconButton>
                  )}
                </div>
              ))}
            </div>
          </div>
        )
      })}

      <AlertDialog open={!!toDelete} onOpenChange={(o) => { if (!o) setToDelete(null) }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Supprimer ce fichier ?</AlertDialogTitle>
            <AlertDialogDescription>Cette action est irréversible.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => setToDelete(null)}>Annuler</AlertDialogCancel>
            <AlertDialogAction onClick={remove}>Supprimer</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
