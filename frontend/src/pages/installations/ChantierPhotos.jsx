// N5 — Photos & fichiers du chantier, groupés avant / pendant / après, avec
// une galerie simple par phase. Réutilise les pièces jointes génériques
// (apps.records, cible installations.installation).
// J43 — porté sur le système de design (Button, IconButton, AlertDialog).
import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useIsAdmin } from '../../hooks/useHasPermission'
import {
  Plus, X, FileText, ChevronLeft, ChevronRight, Images,
} from 'lucide-react'
import recordsApi from '../../api/recordsApi'
import { compressImage } from '../../ui/file-utils'
import {
  Button,
  IconButton,
  Segmented,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
  AlertDialog,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogCancel,
  AlertDialogAction,
} from '../../ui'

// VX149 — densité des vignettes (bascule compact/confortable) : au-delà
// d'une quarantaine de photos par chantier les vignettes fixes size-16
// (64px) devenaient difficiles à parcourir sur un grand chantier ; la
// densité confortable agrandit la vignette, la densité compacte (défaut)
// garde le format actuel.
const DENSITY_KEY = 'taqinor.chantierPhotos.density'
const THUMB_SIZE = { compact: 'size-16', confortable: 'size-24' }

const PHASES = [
  { key: 'avant', label: 'Avant' },
  { key: 'pendant', label: 'Pendant' },
  { key: 'apres', label: 'Après' },
]

const isImage = (a) => (a.mime ?? '').startsWith('image/')

// Garde côté client : taille max 20 Mo, types image/PDF acceptés.
const MAX_SIZE = 20 * 1024 * 1024
const ACCEPTED = ['application/pdf', 'image/png', 'image/jpeg', 'image/webp']

export default function ChantierPhotos({ installationId }) {
  const isAdmin = useIsAdmin()
  const navigate = useNavigate()
  const [items, setItems] = useState([])
  const [busyPhase, setBusyPhase] = useState(null)
  const [toDelete, setToDelete] = useState(null)
  const [uploadError, setUploadError] = useState(null)
  // Lightbox in-app : { phase, index } de l'image affichée (null = fermé).
  const [viewer, setViewer] = useState(null)
  // VX149 — densité des vignettes, persistée (même patron que VIEW_KEY des
  // autres écrans : localStorage, repli propre si indisponible/invalide).
  const [density, setDensity] = useState(() => {
    try {
      const saved = localStorage.getItem(DENSITY_KEY)
      return saved === 'confortable' ? 'confortable' : 'compact'
    } catch {
      return 'compact'
    }
  })
  useEffect(() => {
    try { localStorage.setItem(DENSITY_KEY, density) } catch { /* stockage indisponible */ }
  }, [density])
  const thumbSize = THUMB_SIZE[density]
  const fileRefs = { avant: useRef(null), pendant: useRef(null), apres: useRef(null) }

  const load = () => {
    recordsApi.getAttachments('installations.installation', installationId)
      .then((r) => setItems(r.data.results ?? r.data ?? [])).catch(() => {})
  }
  useEffect(() => { load() }, [installationId]) // eslint-disable-line react-hooks/exhaustive-deps

  const upload = async (phase, file) => {
    if (!file) return
    // N11 — garde taille/type avant l'envoi, message FR explicite.
    if (file.type && !ACCEPTED.includes(file.type)) {
      setUploadError('Format non accepté (images ou PDF uniquement).')
      return
    }
    if (file.size > MAX_SIZE) {
      setUploadError('Fichier trop volumineux (20 Mo maximum).')
      return
    }
    setUploadError(null)
    setBusyPhase(phase)
    try {
      // VX77 — compresse AVANT envoi (bord long ≤1600px, JPEG q0.75) : la
      // photo brute d'un appareil moderne (4-8 Mo) fait caler/timeout la
      // 3G rurale. Les PDF passent intouchés (compressImage() no-op).
      const toSend = await compressImage(file)
      await recordsApi.uploadAttachment('installations.installation', installationId, toSend, phase)
      load()
    } catch {
      setUploadError("Échec de l'envoi. Réessayez.")
    } finally { setBusyPhase(null) }
  }

  const remove = async () => {
    if (!toDelete) return
    try { await recordsApi.deleteAttachment(toDelete.id); load() } catch { /* */ }
    setToDelete(null)
  }

  // L5 — déplacer une pièce jointe entre phases (avant/pendant/après) sans
  // supprimer + ré-uploader : re-tag via l'endpoint records.
  const movePhase = async (att, phase) => {
    if (!phase || phase === (att.phase || 'avant')) return
    setUploadError(null)
    try {
      await recordsApi.setAttachmentPhase(att.id, phase)
      load()
    } catch {
      setUploadError('Déplacement impossible. Réessayez.')
    }
  }

  // Les pièces sans phase (anciennes / génériques) tombent dans « avant » par défaut.
  const byPhase = (key) => items.filter((a) => (a.phase || 'avant') === key)

  // VX44 — compteur de complétion : total de fichiers + nombre de phases
  // couvertes (avant/pendant/après), pour voir d'un coup d'œil ce qu'il reste
  // à documenter sans quitter l'écran.
  const totalFiles = items.length
  const phasesCouvertes = PHASES.filter((p) => byPhase(p.key).length > 0).length

  // N4 — visionneuse : images seules de la phase, navigation préc/suiv.
  const phaseImages = (key) => byPhase(key).filter(isImage)
  const openViewer = (phaseKey, att) => {
    const imgs = phaseImages(phaseKey)
    const index = imgs.findIndex((x) => x.id === att.id)
    if (index >= 0) setViewer({ phase: phaseKey, index })
  }
  const viewerImages = viewer ? phaseImages(viewer.phase) : []
  const viewerAtt = viewer ? viewerImages[viewer.index] : null
  const step = (delta) => setViewer((v) => {
    if (!v) return v
    const imgs = phaseImages(v.phase)
    if (!imgs.length) return null
    const next = (v.index + delta + imgs.length) % imgs.length
    return { ...v, index: next }
  })

  return (
    <div className="flex flex-col gap-3">
      {uploadError && (
        <div className="flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/10 p-2.5 text-sm text-destructive" role="alert">
          <span>{uploadError}</span>
          <Button size="sm" variant="ghost" className="ml-auto" onClick={() => setUploadError(null)}>
            Fermer
          </Button>
        </div>
      )}
      {/* VX227 — lien croisé discret vers les photos terrain des interventions
          de ce chantier (magasins jamais fusionnés, mais navigables). */}
      <div className="flex items-center justify-between gap-2">
        <button type="button"
          onClick={() => navigate(`/interventions?installation=${installationId}`)}
          className="flex items-center gap-1.5 text-[12px] text-muted-foreground underline decoration-dotted underline-offset-2 hover:text-foreground">
          <Images className="size-3.5" aria-hidden="true" />
          Voir aussi les photos de l'intervention
        </button>
      </div>
      {/* VX44 — compteur de complétion des photos du chantier. */}
      <div className="flex items-center gap-2 text-[12px] text-muted-foreground">
        <Images className="size-3.5" aria-hidden="true" />
        <span>
          {totalFiles} photo{totalFiles > 1 ? 's' : ''} · {phasesCouvertes}/{PHASES.length} phase
          {phasesCouvertes > 1 ? 's' : ''} couverte{phasesCouvertes > 1 ? 's' : ''}
        </span>
      </div>
      {/* VX149 — densité des vignettes : utile dès qu'un chantier accumule
          40+ photos, où le format compact fixe devient difficile à parcourir. */}
      <div className="flex items-center justify-end">
        <Segmented
          size="sm"
          value={density}
          onChange={setDensity}
          aria-label="Densité des vignettes"
          options={[
            { value: 'compact', label: 'Compact' },
            { value: 'confortable', label: 'Confortable' },
          ]}
        />
      </div>
      <div className="flex flex-wrap gap-4">
        {PHASES.map((p) => {
          const atts = byPhase(p.key)
          return (
            <div key={p.key} className="min-w-[220px] flex-1">
              <div className="mb-1.5 flex items-center justify-between">
                <strong className="flex items-center gap-1.5 text-sm text-foreground">
                  {p.label} ({atts.length})
                  {/* VX44 — badge sur une phase vide : signale ce qu'il reste
                      à documenter. */}
                  {atts.length === 0 && (
                    <span className="rounded-full bg-warning/15 px-1.5 py-0.5 text-[10px] font-medium text-warning">
                      À compléter
                    </span>
                  )}
                </strong>
                <input ref={fileRefs[p.key]} type="file" className="sr-only"
                       accept="application/pdf,image/png,image/jpeg,image/webp"
                       capture="environment"
                       onChange={(e) => { upload(p.key, e.target.files?.[0]); e.target.value = '' }} />
                <Button type="button" size="sm" variant="outline"
                        loading={busyPhase === p.key}
                        onClick={() => fileRefs[p.key].current?.click()}>
                  {busyPhase === p.key ? null : <Plus />}
                  {busyPhase === p.key ? 'Envoi…' : 'Ajouter'}
                </Button>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {atts.length === 0 && (
                  <span className="text-xs text-muted-foreground">Aucun fichier.</span>
                )}
                {atts.map((a) => (
                  <div key={a.id} className="flex flex-col items-center gap-1">
                    <div className="relative">
                      {isImage(a) ? (
                        <button type="button" title={a.filename}
                                onClick={() => openViewer(p.key, a)}>
                          <img src={a.url} alt={a.filename} loading="lazy"
                               className={`${thumbSize} rounded-md border border-border object-cover`} />
                        </button>
                      ) : (
                        <a href={a.url} target="_blank" rel="noopener noreferrer" title={a.filename}>
                          <span className={`flex ${thumbSize} items-center justify-center rounded-md border border-border bg-muted text-muted-foreground`}>
                            <FileText className="size-6" aria-hidden="true" />
                          </span>
                        </a>
                      )}
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
                    {/* L5 — sélecteur de phase : re-tague la pièce sans ré-upload. */}
                    <Select value={a.phase || 'avant'}
                            onValueChange={(v) => movePhase(a, v)}>
                      <SelectTrigger className="h-6 w-16 px-1.5 text-[11px]"
                                     aria-label="Déplacer vers une autre phase">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {PHASES.map((ph) => (
                          <SelectItem key={ph.key} value={ph.key}>{ph.label}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                ))}
              </div>
            </div>
          )
        })}
      </div>

      {/* N4 — visionneuse plein écran in-app (préc/suiv dans la phase). */}
      {viewerAtt && (
        <div
          className="fixed inset-0 z-[var(--z-overlay)] flex items-center justify-center bg-black/80 p-4"
          role="dialog"
          aria-modal="true"
          onClick={() => setViewer(null)}
        >
          <IconButton
            label="Fermer"
            variant="outline"
            className="absolute right-3 top-3"
            onClick={(e) => { e.stopPropagation(); setViewer(null) }}
          >
            <X />
          </IconButton>
          {viewerImages.length > 1 && (
            <IconButton
              label="Précédent"
              variant="outline"
              className="absolute left-3"
              onClick={(e) => { e.stopPropagation(); step(-1) }}
            >
              <ChevronLeft />
            </IconButton>
          )}
          <img
            src={viewerAtt.url}
            alt={viewerAtt.filename}
            className="max-h-[85vh] max-w-[85vw] rounded-md object-contain"
            onClick={(e) => e.stopPropagation()}
          />
          {viewerImages.length > 1 && (
            <IconButton
              label="Suivant"
              variant="outline"
              className="absolute right-3 top-1/2"
              onClick={(e) => { e.stopPropagation(); step(1) }}
            >
              <ChevronRight />
            </IconButton>
          )}
          <span className="absolute bottom-3 text-xs text-white/80">
            {viewerAtt.filename} · {viewer.index + 1}/{viewerImages.length}
          </span>
        </div>
      )}

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
