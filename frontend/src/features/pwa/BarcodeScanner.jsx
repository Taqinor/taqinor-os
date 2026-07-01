// FG384 — Composant réutilisable de scan code-barres / QR (caméra en direct).
// S'appuie sur le hook `useBarcodeScanner` (API native `BarcodeDetector`, zéro
// dépendance). Rend un flux caméra avec viseur ; à la détection il appelle
// `onDetected(value)`. Repli français explicite quand l'appareil / le
// navigateur ne prend pas en charge `BarcodeDetector`.
//
// Contextes d'usage : réception, picking, relevé de n° de série — le parent
// passe la valeur décodée à l'endpoint existant (stock resolve / recherche
// produit ou série). Ce composant ne fait AUCUN appel réseau lui-même.
import { useEffect } from 'react'
import { ScanLine, CameraOff, X } from 'lucide-react'
import { Button } from '../../ui'
import useBarcodeScanner from './useBarcodeScanner'

const ERROR_MESSAGES = {
  'non-supporte':
    'Le scan par caméra n’est pas pris en charge sur cet appareil / ce '
    + 'navigateur. Saisissez le code manuellement.',
  refuse:
    'Accès à la caméra refusé. Autorisez la caméra puis réessayez, ou saisissez '
    + 'le code manuellement.',
  indisponible:
    'Caméra indisponible. Saisissez le code manuellement.',
}

export default function BarcodeScanner({
  onDetected,
  onClose,
  formats,
  autoStart = true,
  className = '',
}) {
  const { supported, active, error, videoRef, start, stop } = useBarcodeScanner({
    onDetected,
    formats,
  })

  // Démarrage automatique du flux (le hook nettoie la caméra au démontage).
  useEffect(() => {
    if (autoStart && supported) start()
    return () => stop()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoStart, supported])

  // Repli : fonctionnalité absente sur cet appareil / ce navigateur.
  if (!supported) {
    return (
      <div
        role="alert"
        className={`flex flex-col items-center gap-2 rounded-xl border border-border bg-muted/40 p-4 text-center text-sm text-muted-foreground ${className}`}
      >
        <CameraOff className="size-6" aria-hidden="true" />
        <span>{ERROR_MESSAGES['non-supporte']}</span>
        {onClose && (
          <Button size="sm" variant="ghost" onClick={onClose}>Fermer</Button>
        )}
      </div>
    )
  }

  return (
    <div className={`flex flex-col gap-2 ${className}`}>
      <div className="relative overflow-hidden rounded-xl border border-border bg-black">
        <video
          ref={videoRef}
          playsInline
          muted
          className="aspect-video w-full object-cover"
        />
        {/* Viseur de cadrage. */}
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
          <div className="h-1/2 w-2/3 rounded-lg border-2 border-white/80 shadow-[0_0_0_9999px_rgba(0,0,0,0.35)]" />
        </div>
        <div className="pointer-events-none absolute left-1/2 top-2 -translate-x-1/2 rounded-full bg-black/60 px-3 py-1 text-[12px] text-white">
          <span className="flex items-center gap-1.5">
            <ScanLine className="size-3.5" aria-hidden="true" />
            {active ? 'Pointez vers le code…' : 'Démarrage de la caméra…'}
          </span>
        </div>
        {onClose && (
          <button
            type="button"
            onClick={() => { stop(); onClose() }}
            title="Fermer le scanner"
            className="absolute right-2 top-2 rounded-full bg-black/60 p-1.5 text-white"
          >
            <X className="size-4" aria-hidden="true" />
          </button>
        )}
      </div>

      {error && error !== 'non-supporte' && (
        <div
          role="alert"
          className="flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/10 p-2 text-[12px] text-destructive"
        >
          <span>{ERROR_MESSAGES[error] || 'Scan indisponible.'}</span>
          <Button size="sm" variant="ghost" className="ml-auto" onClick={start}>
            Réessayer
          </Button>
        </div>
      )}
    </div>
  )
}
