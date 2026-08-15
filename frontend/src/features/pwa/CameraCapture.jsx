// FG385 — Capture photo caméra en direct (au-delà du simple choix de fichier).
// Ouvre la caméra arrière via `getUserMedia` natif (aucune dépendance npm),
// affiche le flux, et fige une image encodée en JPEG remise au parent sous
// forme de `File` via `onCapture(file, geo)`. Le parent la passe ensuite au
// flux d'upload EXISTANT (installationsApi.ajouterPhoto / recordsApi.
// uploadAttachment) — ce composant ne fait AUCUN appel réseau lui-même
// (hormis la géolocalisation navigateur, best-effort).
//
// NTMOB11 — mode `multiple` : affiche une PELLICULE des photos déjà prises
// dans cette session de capture (miniatures locales) et relance la caméra
// après chaque validation au lieu de fermer, jusqu'à ce que l'utilisateur
// tape « Terminé ». Chaque capture déclenche `navigator.geolocation.
// getCurrentPosition` (best-effort, JAMAIS bloquant si refusé/indisponible —
// `geo` vaut alors `null`) et `onCapture(file, geo)` est appelé
// IMMÉDIATEMENT pour CHAQUE photo (jamais un envoi groupé différé : chaque
// photo doit pouvoir partir/se mettre en file dès sa prise, terrain hors-ligne
// compris — cf. l'outbox générique NTMOB1).
//
// Détection de fonctionnalité : si `getUserMedia` manque, un repli français
// invite à utiliser le choix de fichier ; jamais de plantage.
import { useCallback, useEffect, useRef, useState } from 'react'
import { Camera, CameraOff, RefreshCw, Check, X, ImagePlus } from 'lucide-react'
import { Button } from '../../ui'
import { hapticTap } from '../../lib/haptics'
import useWakeLock from '../../hooks/useWakeLock'

function cameraCaptureSupported() {
  return (
    typeof navigator !== 'undefined'
    && !!navigator.mediaDevices
    && typeof navigator.mediaDevices.getUserMedia === 'function'
    && typeof document !== 'undefined'
  )
}

// NTMOB11 — position best-effort au moment du clic photo : ne bloque JAMAIS
// la capture (timeout court, refus/indisponibilité → `null` silencieux, la
// photo reste pleinement utilisable sans géoloc).
function captureGeoBestEffort() {
  return new Promise((resolve) => {
    if (typeof navigator === 'undefined' || !navigator.geolocation) {
      resolve(null); return
    }
    const done = (geo) => resolve(geo)
    navigator.geolocation.getCurrentPosition(
      (pos) => done({
        latitude: pos.coords.latitude,
        longitude: pos.coords.longitude,
        precision_m: pos.coords.accuracy ?? null,
      }),
      () => done(null),
      { enableHighAccuracy: false, timeout: 4000, maximumAge: 30000 },
    )
  })
}

const ERR = {
  refuse:
    'Accès à la caméra refusé. Autorisez la caméra puis réessayez, ou utilisez '
    + 'le choix de fichier.',
  indisponible: 'Caméra indisponible. Utilisez le choix de fichier.',
}

export default function CameraCapture({
  onCapture,
  onClose,
  filename = 'photo.jpg',
  quality = 0.9,
  className = '',
  // NTMOB11 — capture multi-photos avec pellicule (voir en-tête de fichier).
  multiple = false,
}) {
  const [supported] = useState(cameraCaptureSupported)
  const [active, setActive] = useState(false)
  const [error, setError] = useState(null)
  // NTMOB29 — écran maintenu allumé tant que la caméra est ouverte.
  useWakeLock(active)
  const [preview, setPreview] = useState(null) // dataURL de l'aperçu figé
  // NTMOB11 — miniatures LOCALES des photos déjà validées cette session
  // (mode `multiple` uniquement) ; jamais relu du serveur, purement visuel.
  const [shots, setShots] = useState([])
  const videoRef = useRef(null)
  const streamRef = useRef(null)
  const stoppedRef = useRef(false)
  const blobRef = useRef(null) // Blob de la dernière capture, en attente de validation

  const stopStream = useCallback(() => {
    const stream = streamRef.current
    if (stream) {
      stream.getTracks().forEach((t) => { try { t.stop() } catch { /* déjà coupé */ } })
      streamRef.current = null
    }
    if (videoRef.current) {
      try { videoRef.current.srcObject = null } catch { /* ignore */ }
    }
    setActive(false)
  }, [])

  const start = useCallback(async () => {
    if (!supported) { setError('indisponible'); return }
    setError(null); setPreview(null); blobRef.current = null
    stoppedRef.current = false
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: 'environment' } },
        audio: false,
      })
      if (stoppedRef.current) { stream.getTracks().forEach((t) => t.stop()); return }
      streamRef.current = stream
      const video = videoRef.current
      if (video) {
        video.srcObject = stream
        video.setAttribute('playsinline', 'true')
        await video.play().catch(() => { /* autoplay bloqué : ignore */ })
      }
      setActive(true)
    } catch (err) {
      setError(err && err.name === 'NotAllowedError' ? 'refuse' : 'indisponible')
      stopStream()
    }
  }, [supported, stopStream])

  // Fige l'image courante du flux dans un canvas → Blob JPEG.
  const snap = useCallback(() => {
    const video = videoRef.current
    if (!video || !video.videoWidth) return
    const canvas = document.createElement('canvas')
    canvas.width = video.videoWidth
    canvas.height = video.videoHeight
    const ctx = canvas.getContext('2d')
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height)
    setPreview(canvas.toDataURL('image/jpeg', quality))
    canvas.toBlob((blob) => { blobRef.current = blob }, 'image/jpeg', quality)
    // On fige : coupe le flux caméra tant que l'utilisateur décide.
    stopStream()
  }, [quality, stopStream])

  // Reprend une nouvelle photo (relance le flux).
  const retake = useCallback(() => { setPreview(null); blobRef.current = null; start() }, [start])

  // Nom de fichier unique par prise (mode `multiple` : la valeur par défaut
  // partagée collisionnerait sinon entre plusieurs photos de la même étape).
  const nextFilename = useCallback((n) => {
    if (!multiple) return filename
    const dot = filename.lastIndexOf('.')
    const base = dot > 0 ? filename.slice(0, dot) : filename
    const ext = dot > 0 ? filename.slice(dot) : '.jpg'
    return `${base}-${n + 1}${ext}`
  }, [filename, multiple])

  // Valide l'aperçu : capture la géoloc best-effort, construit le File et le
  // remet au flux d'upload existant. En mode `multiple`, ajoute à la
  // pellicule locale et relance la caméra au lieu de fermer.
  const confirm = useCallback(async () => {
    const blob = blobRef.current
    if (!blob) return
    const geo = await captureGeoBestEffort()
    const file = new File([blob], nextFilename(shots.length), { type: 'image/jpeg' })
    onCapture?.(file, geo)
    hapticTap()
    if (multiple) {
      const thumbUrl = URL.createObjectURL(blob)
      setShots((prev) => [...prev, { id: `${Date.now()}-${prev.length}`, url: thumbUrl }])
      setPreview(null); blobRef.current = null
      start()
      return
    }
    setPreview(null); blobRef.current = null
    onClose?.()
  }, [multiple, nextFilename, onCapture, onClose, shots.length, start])

  // Libère les URLs objet des miniatures de la pellicule (mode `multiple`).
  const releaseShots = useCallback(() => {
    setShots((prev) => {
      prev.forEach((s) => { try { URL.revokeObjectURL(s.url) } catch { /* déjà libéré */ } })
      return []
    })
  }, [])

  const close = useCallback(() => {
    stoppedRef.current = true
    stopStream()
    releaseShots()
    onClose?.()
  }, [stopStream, releaseShots, onClose])

  // Démarrage auto + libération de la caméra au démontage. Démarrage déféré
  // pour éviter un setState synchrone dans l'effet.
  useEffect(() => {
    const raf = supported ? requestAnimationFrame(() => start()) : null
    return () => {
      if (raf) cancelAnimationFrame(raf)
      stoppedRef.current = true
      stopStream()
      releaseShots() // NTMOB11 — libère les URLs objet même sans close() explicite.
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  if (!supported) {
    return (
      <div
        role="alert"
        className={`flex flex-col items-center gap-2 rounded-xl border border-border bg-muted/40 p-4 text-center text-sm text-muted-foreground ${className}`}
      >
        <CameraOff className="size-6" aria-hidden="true" />
        <span>
          La prise de photo en direct n’est pas prise en charge sur cet appareil /
          ce navigateur. Utilisez le choix de fichier.
        </span>
        {onClose && <Button size="sm" variant="ghost" onClick={onClose}>Fermer</Button>}
      </div>
    )
  }

  return (
    <div className={`flex flex-col gap-2 ${className}`}>
      <div className="relative overflow-hidden rounded-xl border border-border bg-black">
        {preview ? (
          <img src={preview} alt="Aperçu de la photo"
            className="aspect-video w-full object-contain" />
        ) : (
          <video ref={videoRef} playsInline muted
            className="aspect-video w-full object-cover" />
        )}
        {onClose && (
          <button type="button" onClick={close} title="Fermer la caméra"
            className="absolute right-2 top-2 rounded-full bg-black/60 p-1.5 text-white">
            <X className="size-4" aria-hidden="true" />
          </button>
        )}
      </div>

      {/* NTMOB11 — pellicule des photos déjà prises cette session (mode
          `multiple`), avant validation finale. Purement visuel (miniatures
          locales), jamais relu du serveur. */}
      {multiple && shots.length > 0 && (
        <div className="flex items-center gap-2 overflow-x-auto pb-1" aria-label="Photos déjà prises">
          {shots.map((s) => (
            <img key={s.id} src={s.url} alt="" aria-hidden="true"
              className="size-12 shrink-0 rounded-md border border-border object-cover" />
          ))}
          <span className="shrink-0 text-xs text-muted-foreground">
            {shots.length} photo{shots.length > 1 ? 's' : ''}
          </span>
        </div>
      )}

      {error ? (
        <div role="alert"
          className="flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/10 p-2 text-[12px] text-destructive">
          <span>{ERR[error] || 'Caméra indisponible.'}</span>
          <Button size="sm" variant="ghost" className="ml-auto" onClick={start}>
            Réessayer
          </Button>
        </div>
      ) : preview ? (
        <div className="flex items-center gap-2">
          <Button size="sm" onClick={confirm}>
            <Check className="size-4" aria-hidden="true" />
            {multiple ? 'Garder et continuer' : 'Utiliser cette photo'}
          </Button>
          <Button size="sm" variant="outline" onClick={retake}>
            <RefreshCw className="size-4" aria-hidden="true" /> Reprendre
          </Button>
        </div>
      ) : (
        <div className="flex items-center gap-2">
          <Button size="sm" disabled={!active} onClick={snap}>
            <Camera className="size-4" aria-hidden="true" />
            {multiple && shots.length > 0 ? 'Photo suivante' : 'Prendre la photo'}
          </Button>
          {/* NTMOB11 — validation finale de la pellicule (mode `multiple`). */}
          {multiple && shots.length > 0 && (
            <Button size="sm" variant="secondary" onClick={close}>
              <ImagePlus className="size-4" aria-hidden="true" /> Terminé
            </Button>
          )}
        </div>
      )}
    </div>
  )
}
