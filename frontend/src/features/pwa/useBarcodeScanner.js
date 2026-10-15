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
import { attacherFlux } from './flux'

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
  const frameAvertie = useRef(false) // une seule trace console par session de scan
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
      stream.getTracks().forEach((t) => { try { t.stop() } catch (err) { console.warn('useBarcodeScanner.useBarcodeScanner : déjà coupé', err) } })
      streamRef.current = null
    }
    if (videoRef.current) {
      try { videoRef.current.srcObject = null } catch (err) { console.warn('useBarcodeScanner.useBarcodeScanner : ignore', err) }
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
      await attacherFlux(videoRef.current, stream)
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
        } catch (err) {
          // Frame non prête : on réessaie — une seule trace pour ne pas inonder la console (1 appel / image).
          if (!frameAvertie.current) { frameAvertie.current = true; console.warn('useBarcodeScanner.tick : frame non prête', err) }
        }
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
