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
import installationsApi from '../../api/installationsApi'
import { formatDate } from '../../lib/format'
import { compressPhotoForUpload } from '../preferences/prefs'
import DataSaverThumb from '../../features/pwa/DataSaverThumb'
import {
  Button,
  IconButton,
  Badge,
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

/* ============================================================================
   APX27 — Vue « Comparer » : une paire avant/après (appariée par ordre
   d'ajout) avec un séparateur glissant CSS-only. L'interaction vit sur un
   <input type="range"> natif étiré sur toute la carte (piloté au clavier ET
   au doigt/souris, cible tactile largement ≥44 px) qui pose une variable CSS
   (`--apx27-pos`) consommée par `clip-path` sur la photo « avant » — AUCUNE
   bibliothèque de drag, zéro dépendance nouvelle. Aucune transition/animation
   n'est posée sur le déplacement (suivi 1:1 de la position du curseur) : la
   contrainte reduced-motion est donc satisfaite par construction, sans bloc
   dédié — rien à réduire.
   ========================================================================== */
function BeforeAfterCompare({ before, after, index }) {
  const [pos, setPos] = useState(50)
  return (
    <figure className="apx27-compare-card">
      <div className="apx27-compare" style={{ '--apx27-pos': `${pos}%` }}>
        <img
          src={after.url}
          alt={`Après — ${after.filename || ''}`}
          loading="lazy"
          className="apx27-compare-img apx27-compare-img--after"
        />
        <img
          src={before.url}
          alt={`Avant — ${before.filename || ''}`}
          loading="lazy"
          className="apx27-compare-img apx27-compare-img--before"
        />
        <span className="apx27-compare-tag apx27-compare-tag--before" aria-hidden="true">Avant</span>
        <span className="apx27-compare-tag apx27-compare-tag--after" aria-hidden="true">Après</span>
        <span className="apx27-compare-handle" aria-hidden="true" />
        <input
          type="range"
          min={0}
          max={100}
          value={pos}
          onChange={(e) => setPos(Number(e.target.value))}
          className="apx27-compare-slider"
          aria-label={`Comparaison ${index + 1} — glisser pour révéler avant/après`}
        />
      </div>
    </figure>
  )
}

export default function ChantierPhotos({ installationId }) {
  const isAdmin = useIsAdmin()
  const navigate = useNavigate()
  const [items, setItems] = useState([])
  const [busyPhase, setBusyPhase] = useState(null)
  const [toDelete, setToDelete] = useState(null)
  const [uploadError, setUploadError] = useState(null)
  // APX27 — galerie unifiée EN LECTURE : photos des interventions liées à ce
  // chantier (shot-list F7/F8), fusionnées avec les pièces jointes chantier
  // ci-dessus par phase (avant/pendant/après — même vocabulaire des deux
  // côtés). AUCUN nouveau modèle : les deux sources sont déjà des
  // `records.Attachment`, seulement rattachées à des objets différents.
  const [interventionPhotos, setInterventionPhotos] = useState([])
  // APX27 — bascule Galerie (existant, désormais unifiée) / Comparer.
  const [view, setView] = useState('galerie')
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

  // APX27 — charge les photos des interventions rattachées à ce chantier
  // (mêmes clés de phase que ci-dessus, `installationsApi.getPhotos` déjà
  // servi par F7/F8) et les aplatit en une seule liste taguée `origin`.
  // Best-effort : une intervention dont les photos ne chargent pas ne bloque
  // pas les autres (Promise.all sur des promesses déjà `.catch()`ées).
  const loadInterventionPhotos = () => {
    if (!installationId) { setInterventionPhotos([]); return }
    installationsApi.getInterventions({ installation: installationId })
      .then((r) => {
        const list = r.data?.results ?? r.data ?? []
        return Promise.all(list.map((interv) => installationsApi.getPhotos(interv.id)
          .then((pr) => ({ interv, groupes: pr.data?.groupes ?? {} }))
          .catch(() => ({ interv, groupes: {} }))))
      })
      .then((entries) => {
        const flat = []
        entries.forEach(({ interv, groupes }) => {
          const when = interv.date_realisee || interv.date_prevue
          const originLabel = [interv.type_intervention_display, when ? formatDate(when) : null]
            .filter(Boolean).join(' — ') || 'Intervention'
          PHASES.forEach((p) => {
            (groupes[p.key] ?? []).forEach((slot) => {
              (slot.photos ?? []).forEach((photo) => {
                flat.push({
                  ...photo,
                  phase: p.key,
                  origin: 'intervention',
                  interventionId: interv.id,
                  originLabel,
                })
              })
            })
          })
        })
        setInterventionPhotos(flat)
      })
      .catch(() => setInterventionPhotos([]))
  }
  // Chargement des photos d'intervention au changement de chantier (motif de
  // fetch standard : l'etat est pose dans les callbacks de la promesse).
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { loadInterventionPhotos() }, [installationId]) // eslint-disable-line react-hooks/exhaustive-deps

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
      // NTMOB12 — respecte la préférence « Qualité photo » (Mes préférences) :
      // passthrough total si l'utilisateur a choisi Original.
      const toSend = await compressPhotoForUpload(file)
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

  // APX27 — galerie unifiée (chantier + interventions liées) par phase,
  // chantier d'abord (ordre d'ajout historique inchangé) puis interventions.
  const byPhaseAll = (key) => [
    ...items.filter((a) => (a.phase || 'avant') === key).map((a) => ({ ...a, origin: 'chantier' })),
    ...interventionPhotos.filter((p) => p.phase === key),
  ]

  // VX44 — compteur de complétion : total de fichiers + nombre de phases
  // couvertes (avant/pendant/après), pour voir d'un coup d'œil ce qu'il reste
  // à documenter sans quitter l'écran. Reste volontairement scopé au chantier
  // (sa propre obligation documentaire) — les photos d'intervention ne sont
  // pas SA documentation, seulement visibles en galerie unifiée à côté.
  const totalFiles = items.length
  const phasesCouvertes = PHASES.filter((p) => byPhase(p.key).length > 0).length

  // N4/APX27 — visionneuse : images de la phase, chantier + interventions
  // (galerie unifiée « en lecture »), navigation préc/suiv sans distinction
  // de source (l'id d'Attachment est unique tous propriétaires confondus).
  const phaseImages = (key) => byPhaseAll(key).filter(isImage)
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

  // APX27 — vue « Comparer » : appariement avant/après PAR ORDRE (aucune
  // métadonnée ne relie une photo « avant » précise à SON « après » — la
  // seule donnée fiable est l'ordre d'ajout, déjà celui rendu par la
  // galerie), sur la galerie UNIFIÉE (chantier + interventions). Les photos
  // en surplus d'un côté (comptes différents) restent visibles à part —
  // jamais une paire inventée avec une image manquante.
  const compareAvant = phaseImages('avant')
  const compareApres = phaseImages('apres')
  const comparePairs = Array.from(
    { length: Math.min(compareAvant.length, compareApres.length) },
    (_, i) => ({ before: compareAvant[i], after: compareApres[i] }),
  )
  const compareSurplusAvant = compareAvant.slice(comparePairs.length)
  const compareSurplusApres = compareApres.slice(comparePairs.length)

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
      {/* APX27 — Galerie (chantier + interventions, unifiée) / Comparer
          (paires avant/après). VX149 — densité des vignettes : n'a de sens
          qu'en Galerie. */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Segmented
          size="sm"
          value={view}
          onChange={setView}
          aria-label="Mode d'affichage des photos"
          options={[
            { value: 'galerie', label: 'Galerie' },
            { value: 'comparer', label: 'Comparer' },
          ]}
        />
        {view === 'galerie' && (
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
        )}
      </div>

      {view === 'galerie' && (
        <div className="flex flex-wrap gap-4">
          {PHASES.map((p) => {
            const atts = byPhaseAll(p.key)
            // VX44 — le nudge « À compléter » reste l'obligation PROPRE du
            // chantier (comme le compteur d'en-tête ci-dessus) : une phase
            // documentée uniquement par une intervention liée n'éteint pas
            // l'incitation, sinon la galerie unifiée masquerait un vrai trou.
            const chantierManquant = byPhase(p.key).length === 0
            return (
              <div key={p.key} className="min-w-[220px] flex-1">
                <div className="mb-1.5 flex items-center justify-between">
                  <strong className="flex items-center gap-1.5 text-sm text-foreground">
                    {p.label} ({atts.length})
                    {/* VX44 — badge sur une phase vide : signale ce qu'il reste
                        à documenter. */}
                    {chantierManquant && (
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
                          // NTMOB17 — en mode économie de données la vignette
                          // n'est chargée qu'au tap (aucune requête image sinon).
                          <DataSaverThumb
                            src={a.url}
                            alt={a.filename}
                            title={a.filename}
                            className={`${thumbSize} rounded-md border border-border object-cover`}
                            onActivate={() => openViewer(p.key, a)}
                          />
                        ) : (
                          <a href={a.url} target="_blank" rel="noopener noreferrer" title={a.filename}>
                            <span className={`flex ${thumbSize} items-center justify-center rounded-md border border-border bg-muted text-muted-foreground`}>
                              <FileText className="size-6" aria-hidden="true" />
                            </span>
                          </a>
                        )}
                        {isAdmin && a.origin !== 'intervention' && (
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
                      {/* APX27 — badge d'origine : une photo d'intervention est
                          EN LECTURE ici (pas de re-tag/suppression — elle
                          appartient à SA fiche intervention). */}
                      {a.origin === 'intervention' ? (
                        <Badge tone="info" className="max-w-16 truncate text-[10px]" title={a.originLabel}>
                          {a.originLabel}
                        </Badge>
                      ) : (
                        /* L5 — sélecteur de phase : re-tague la pièce sans ré-upload. */
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
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )
          })}
        </div>
      )}

      {view === 'comparer' && (
        <div className="flex flex-col gap-3">
          {comparePairs.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Ajoutez au moins une photo « Avant » ET une « Après » (chantier ou
              intervention) pour activer la comparaison.
            </p>
          ) : (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {comparePairs.map((pair, i) => (
                <BeforeAfterCompare key={`${pair.before.id}-${pair.after.id}`} before={pair.before} after={pair.after} index={i} />
              ))}
            </div>
          )}
          {(compareSurplusAvant.length > 0 || compareSurplusApres.length > 0) && (
            <p className="text-xs text-muted-foreground">
              {compareSurplusAvant.length > 0 && (
                <>{compareSurplusAvant.length} photo{compareSurplusAvant.length > 1 ? 's' : ''} « Avant » sans « Après » correspondante. </>
              )}
              {compareSurplusApres.length > 0 && (
                <>{compareSurplusApres.length} photo{compareSurplusApres.length > 1 ? 's' : ''} « Après » sans « Avant » correspondante.</>
              )}
            </p>
          )}
        </div>
      )}

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
