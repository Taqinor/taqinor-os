// NTMOB13 — Scan de documents structuré vers OCR. Variante RÉUTILISABLE du
// pipeline caméra→canvas déjà établi par l'écran « Numériser » (XGED12,
// features/ged) : capture UNE photo via CameraCapture, tente un recadrage
// AUTOMATIQUE par détection de contour simple (analyse de contraste,
// documentScan.js — aucune dépendance externe), puis affiche TOUJOURS un
// panneau de recadrage manuel (4 curseurs de marge) — pré-rempli par la
// détection quand elle est confiante, à 0 (cadre entier) sinon : c'est le
// « repli sur recadrage manuel si la détection échoue » de la spec, unifié
// dans un seul écran de révision plutôt que deux chemins séparés.
//
// `onScan(file, geo)` reçoit le fichier RECADRÉ final (JPEG) — le parent le
// branche sur son propre flux d'upload (ex. le pipeline OCR de
// stock/ocr-import, apps.stock.ocr_import côté serveur — inchangé, ce
// composant ne fait AUCUN appel réseau lui-même).
import { useCallback, useRef, useState } from 'react'
import { Check, RefreshCw, ScanLine, Sparkles } from 'lucide-react'
import { Button, Badge, Slider } from '../../ui'
import CameraCapture from './CameraCapture'
import {
  toGrayscale, detectDocumentBounds, boundsToInsets, insetsToBounds,
  MIN_CONFIDENCE,
} from './documentScan'

const ZERO_INSETS = { top: 0, right: 0, bottom: 0, left: 0 }

// Charge un File image → { img, width, height } (dimensions naturelles).
function loadImageFile(file) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file)
    const img = new Image()
    img.onload = () => {
      URL.revokeObjectURL(url)
      resolve({ img, width: img.naturalWidth, height: img.naturalHeight })
    }
    img.onerror = () => { URL.revokeObjectURL(url); reject(new Error('image illisible')) }
    img.src = url
  })
}

export default function DocumentScanCapture({
  onScan, onClose, filename = 'scan.jpg', quality = 0.9, className = '',
}) {
  const [phase, setPhase] = useState('camera') // camera | detecting | review
  const [previewUrl, setPreviewUrl] = useState(null)
  const [insets, setInsets] = useState(ZERO_INSETS)
  const [autoDetected, setAutoDetected] = useState(false)
  const imgRef = useRef(null) // Image DOM chargée (dimensions naturelles), pour le recadrage final.
  const geoRef = useRef(null)

  const resetToCamera = useCallback(() => {
    if (previewUrl) URL.revokeObjectURL(previewUrl)
    setPreviewUrl(null); setInsets(ZERO_INSETS); setAutoDetected(false)
    imgRef.current = null; geoRef.current = null
    setPhase('camera')
  }, [previewUrl])

  // NTMOB13 — après la capture brute, tente la détection automatique de
  // contour (best-effort : toute erreur retombe silencieusement sur le
  // recadrage manuel à 0, jamais un blocage de la capture).
  const handleRawCapture = useCallback(async (file, geo) => {
    geoRef.current = geo ?? null
    setPhase('detecting')
    try {
      const { img, width, height } = await loadImageFile(file)
      imgRef.current = img
      setPreviewUrl(URL.createObjectURL(file))

      const canvas = document.createElement('canvas')
      canvas.width = width
      canvas.height = height
      const ctx = canvas.getContext('2d')
      ctx.drawImage(img, 0, 0, width, height)
      const { data } = ctx.getImageData(0, 0, width, height)
      const bounds = detectDocumentBounds(toGrayscale(data), width, height)

      if (bounds.confidence >= MIN_CONFIDENCE) {
        setInsets(boundsToInsets(bounds, width, height))
        setAutoDetected(true)
      } else {
        setInsets(ZERO_INSETS)
        setAutoDetected(false)
      }
    } catch {
      // Détection indisponible (canvas/Image en échec) : repli manuel à 0,
      // la photo pleine reste pleinement utilisable.
      setInsets(ZERO_INSETS)
      setAutoDetected(false)
    } finally {
      setPhase('review')
    }
  }, [])

  const setInset = (edge, value) =>
    setInsets((prev) => ({ ...prev, [edge]: value }))

  // Applique le recadrage final (insets → rectangle pixels) et remet le
  // fichier recadré à l'appelant.
  const confirm = useCallback(() => {
    const img = imgRef.current
    if (!img) return
    const width = img.naturalWidth
    const height = img.naturalHeight
    const box = insetsToBounds(insets, width, height)
    const canvas = document.createElement('canvas')
    canvas.width = box.width
    canvas.height = box.height
    const ctx = canvas.getContext('2d')
    ctx.drawImage(
      img, box.x, box.y, box.width, box.height, 0, 0, box.width, box.height)
    canvas.toBlob((blob) => {
      if (!blob) return
      const file = new File([blob], filename, { type: 'image/jpeg' })
      onScan?.(file, geoRef.current)
      resetToCamera()
      onClose?.()
    }, 'image/jpeg', quality)
  }, [insets, filename, quality, onScan, onClose, resetToCamera])

  if (phase === 'camera' || phase === 'detecting') {
    return (
      <div className={className}>
        <CameraCapture
          filename={filename}
          onCapture={handleRawCapture}
          onClose={onClose}
        />
        {phase === 'detecting' && (
          <p className="mt-2 flex items-center gap-1.5 text-xs text-muted-foreground">
            <ScanLine className="size-3.5 animate-pulse" aria-hidden="true" />
            Détection du document…
          </p>
        )}
      </div>
    )
  }

  // phase === 'review'. Repli défensif : si l'image n'a même pas pu être
  // chargée (échec canvas/Image, rarissime), on ne montre jamais un écran de
  // révision cassé — juste une invite à reprendre la photo.
  if (!previewUrl || !imgRef.current) {
    return (
      <div className={`flex flex-col gap-3 ${className}`}>
        <p className="text-sm text-muted-foreground">
          La photo n'a pas pu être chargée pour le recadrage. Réessayez.
        </p>
        <Button size="sm" variant="outline" onClick={resetToCamera}>
          <RefreshCw className="size-4" aria-hidden="true" /> Reprendre la photo
        </Button>
      </div>
    )
  }

  return (
    <div className={`flex flex-col gap-3 ${className}`}>
      <div className="relative overflow-hidden rounded-xl border border-border bg-black">
        <img src={previewUrl} alt="Document capturé" className="block w-full" />
        {/* Overlay du rectangle de recadrage courant, en % — coût nul au
            glissement des curseurs (pas de redessin canvas avant validation). */}
        <div
          className="pointer-events-none absolute border-2 border-primary shadow-[0_0_0_9999px_rgba(0,0,0,0.45)]"
          style={{
            top: `${insets.top}%`, left: `${insets.left}%`,
            right: `${insets.right}%`, bottom: `${insets.bottom}%`,
          }}
        />
      </div>

      <Badge tone={autoDetected ? 'success' : 'neutral'} className="w-fit">
        {autoDetected
          ? <><Sparkles className="size-3" aria-hidden="true" /> Document détecté — ajustez si besoin</>
          : 'Recadrage manuel — ajustez les bords du document'}
      </Badge>

      <div className="grid grid-cols-2 gap-x-4 gap-y-2">
        {(['top', 'left', 'right', 'bottom']).map((edge) => (
          <label key={edge} className="flex flex-col gap-1 text-xs text-muted-foreground">
            {{ top: 'Haut', left: 'Gauche', right: 'Droite', bottom: 'Bas' }[edge]}
            <Slider
              value={[insets[edge]]}
              onValueChange={([v]) => setInset(edge, v)}
              min={0} max={45} step={1}
              aria-label={`Marge ${edge === 'top' ? 'haute' : edge === 'left' ? 'gauche' : edge === 'right' ? 'droite' : 'basse'}`}
            />
          </label>
        ))}
      </div>

      <div className="flex items-center gap-2">
        <Button size="sm" onClick={confirm}>
          <Check className="size-4" aria-hidden="true" /> Valider et envoyer à l'OCR
        </Button>
        <Button size="sm" variant="outline" onClick={resetToCamera}>
          <RefreshCw className="size-4" aria-hidden="true" /> Reprendre la photo
        </Button>
      </div>
    </div>
  )
}
