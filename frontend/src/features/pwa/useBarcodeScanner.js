// FG384 — Hook réutilisable de scan code-barres / QR via l'API native
// `BarcodeDetector` (aucune librairie externe). Ouvre la caméra arrière avec
// `getUserMedia`, détecte en boucle un code-barres/QR et renvoie sa valeur
// décodée. Détection de fonctionnalité stricte : si `BarcodeDetector` ou
// `getUserMedia` manque (Safari, Firefox…), le hook expose `supported=false`
// pour qu'un repli français soit affiché — jamais de plantage.
//
// Usage :
//   const { supported, active, error, videoRef, start, stop } =
//     useBarcodeScanner({ onDetected: (value) => …, formats })
//   <video ref={videoRef} playsInline muted />
import { useCallback, useEffect, useRef, useState } from 'react'
import { hapticTap } from '../../lib/haptics'

// Vrai si les deux briques natives requises existent dans ce navigateur.
export function barcodeScanSupported() {
  return (
    typeof window !== 'undefined'
    && 'BarcodeDetector' in window
    && typeof navigator !== 'undefined'
    && !!navigator.mediaDevices
    && typeof navigator.mediaDevices.getUserMedia === 'function'
  )
}

// Formats par défaut couvrant les étiquettes internes (QR) et les codes-barres
// linéaires courants du matériel solaire.
const DEFAULT_FORMATS = [
  'qr_code', 'code_128', 'ean_13', 'ean_8', 'code_39', 'upc_a', 'upc_e',
  'itf', 'data_matrix',
]

export function useBarcodeScanner({ onDetected, formats } = {}) {
  const [supported] = useState(barcodeScanSupported)
  const [active, setActive] = useState(false)
  const [error, setError] = useState(null)
  const videoRef = useRef(null)
  const streamRef = useRef(null)
  const detectorRef = useRef(null)
  const rafRef = useRef(null)
  const stoppedRef = useRef(false)
  // Garde la dernière valeur pour ne pas rappeler `onDetected` en rafale sur
  // le même code (la boucle tourne plusieurs fois par seconde).
  const lastValueRef = useRef(null)
  const onDetectedRef = useRef(onDetected)
  useEffect(() => { onDetectedRef.current = onDetected }, [onDetected])

  // Coupe la caméra et la boucle de détection. Idempotent.
  const stop = useCallback(() => {
    stoppedRef.current = true
    if (rafRef.current) {
      cancelAnimationFrame(rafRef.current)
      rafRef.current = null
    }
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
    if (!supported) {
      setError('non-supporte')
      return
    }
    setError(null)
    stoppedRef.current = false
    lastValueRef.current = null
    try {
      if (!detectorRef.current) {
        detectorRef.current = new BarcodeDetector({
          formats: formats && formats.length ? formats : DEFAULT_FORMATS,
        })
      }
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: 'environment' } },
        audio: false,
      })
      if (stoppedRef.current) {
        // Le composant a été fermé pendant la demande d'autorisation.
        stream.getTracks().forEach((t) => t.stop())
        return
      }
      streamRef.current = stream
      const video = videoRef.current
      if (video) {
        video.srcObject = stream
        video.setAttribute('playsinline', 'true')
        await video.play().catch(() => { /* autoplay bloqué : ignore */ })
      }
      setActive(true)

      const tick = async () => {
        if (stoppedRef.current || !detectorRef.current || !videoRef.current) return
        try {
          const codes = await detectorRef.current.detect(videoRef.current)
          if (codes && codes.length) {
            const value = (codes[0].rawValue || '').trim()
            if (value && value !== lastValueRef.current) {
              lastValueRef.current = value
              hapticTap()
              onDetectedRef.current?.(value)
            }
          }
        } catch { /* frame non prête : on réessaie */ }
        if (!stoppedRef.current) rafRef.current = requestAnimationFrame(tick)
      }
      rafRef.current = requestAnimationFrame(tick)
    } catch (err) {
      // Autorisation refusée / caméra indisponible.
      setError(err && err.name === 'NotAllowedError' ? 'refuse' : 'indisponible')
      stop()
    }
  }, [supported, formats, stop])

  // Libère toujours la caméra au démontage.
  useEffect(() => () => { stop() }, [stop])

  return { supported, active, error, videoRef, start, stop }
}

export default useBarcodeScanner
