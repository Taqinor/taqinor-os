// FG385 — Capture photo caméra en direct (au-delà du simple choix de fichier).
// Ouvre la caméra arrière via `getUserMedia` natif (aucune dépendance npm),
// affiche le flux, et fige une image encodée en JPEG remise au parent sous
// forme de `File` via `onCapture(file)`. Le parent la passe ensuite au flux
// d'upload EXISTANT (installationsApi.ajouterPhoto / recordsApi.uploadAttachment)
// — ce composant ne fait AUCUN appel réseau.
//
// Détection de fonctionnalité : si `getUserMedia` manque, un repli français
// invite à utiliser le choix de fichier ; jamais de plantage.
import { useCallback, useEffect, useRef, useState } from 'react'
import { Camera, CameraOff, RefreshCw, Check, X } from 'lucide-react'
import { Button } from '../../ui'
import { hapticTap } from '../../lib/haptics'

function cameraCaptureSupported() {
  return (
    typeof navigator !== 'undefined'
    && !!navigator.mediaDevices
    && typeof navigator.mediaDevices.getUserMedia === 'function'
    && typeof document !== 'undefined'
  )
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
}) {
  const [supported] = useState(cameraCaptureSupported)
  const [active, setActive] = useState(false)
  const [error, setError] = useState(null)
  const [preview, setPreview] = useState(null) // dataURL de l'aperçu figé
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

  // Valide l'aperçu : construit le File et le remet au flux d'upload existant.
  const confirm = useCallback(() => {
    const blob = blobRef.current
    if (!blob) return
    const file = new File([blob], filename, { type: 'image/jpeg' })
    onCapture?.(file)
    hapticTap()
    setPreview(null); blobRef.current = null
    onClose?.()
  }, [filename, onCapture, onClose])

  const close = useCallback(() => {
    stoppedRef.current = true
    stopStream()
    onClose?.()
  }, [stopStream, onClose])

  // Démarrage auto + libération de la caméra au démontage. Démarrage déféré
  // pour éviter un setState synchrone dans l'effet.
  useEffect(() => {
    const raf = supported ? requestAnimationFrame(() => start()) : null
    return () => {
      if (raf) cancelAnimationFrame(raf)
      stoppedRef.current = true
      stopStream()
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
            <Check className="size-4" aria-hidden="true" /> Utiliser cette photo
          </Button>
          <Button size="sm" variant="outline" onClick={retake}>
            <RefreshCw className="size-4" aria-hidden="true" /> Reprendre
          </Button>
        </div>
      ) : (
        <Button size="sm" disabled={!active} onClick={snap}>
          <Camera className="size-4" aria-hidden="true" /> Prendre la photo
        </Button>
      )}
    </div>
  )
}
