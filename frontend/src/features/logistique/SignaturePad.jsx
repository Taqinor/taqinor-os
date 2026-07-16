// XSTK2 — Pad de signature tracée (canvas), même esprit que la signature
// client FG69 (`installations.Intervention.signature_client` — data-URL PNG).
// Aucun composant canvas de signature réutilisable n'existait ailleurs dans le
// frontend (FG69 backend n'a pas d'écran de trace dédié) ; ce petit composant
// LOCAL au module Logistique produit la même forme de donnée (data-URL PNG)
// attendue par `PreuveLivraison.signature_data`. Pointeur souris + tactile via
// Pointer Events (aucune dépendance npm). `onChange(dataUrl|null)` remonte la
// signature courante ; le parent gère l'appel réseau (mêmes conventions que
// `CameraCapture` : ce composant ne fait AUCUN appel réseau).
import { useCallback, useEffect, useRef, useState } from 'react'
import { Eraser } from 'lucide-react'
import { Button } from '../../ui'
import { hapticTap } from '../../lib/haptics'

export default function SignaturePad({ onChange, className = '', height = 160 }) {
  const canvasRef = useRef(null)
  const drawingRef = useRef(false)
  const emptyRef = useRef(true)
  const [empty, setEmpty] = useState(true)

  const ctx = useCallback(() => canvasRef.current?.getContext('2d') ?? null, [])

  const resize = useCallback(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ratio = window.devicePixelRatio || 1
    const rect = canvas.getBoundingClientRect()
    canvas.width = Math.max(1, Math.round(rect.width * ratio))
    canvas.height = Math.max(1, Math.round(rect.height * ratio))
    const c = ctx()
    if (c) {
      c.scale(ratio, ratio)
      c.lineWidth = 2
      c.lineCap = 'round'
      c.lineJoin = 'round'
      c.strokeStyle = '#111'
    }
  }, [ctx])

  useEffect(() => {
    resize()
    window.addEventListener('resize', resize)
    return () => window.removeEventListener('resize', resize)
  }, [resize])

  const point = (e) => {
    const canvas = canvasRef.current
    const rect = canvas.getBoundingClientRect()
    return { x: e.clientX - rect.left, y: e.clientY - rect.top }
  }

  const start = (e) => {
    drawingRef.current = true
    const c = ctx()
    const { x, y } = point(e)
    c?.beginPath()
    c?.moveTo(x, y)
    e.currentTarget.setPointerCapture?.(e.pointerId)
  }

  const move = (e) => {
    if (!drawingRef.current) return
    const c = ctx()
    const { x, y } = point(e)
    c?.lineTo(x, y)
    c?.stroke()
    if (emptyRef.current) {
      emptyRef.current = false
      setEmpty(false)
      // VX42 — retour haptique au premier trait tracé (signature capturée).
      hapticTap()
    }
  }

  const end = () => {
    if (!drawingRef.current) return
    drawingRef.current = false
    if (!emptyRef.current) {
      onChange?.(canvasRef.current?.toDataURL('image/png') ?? null)
    }
  }

  const clear = () => {
    const canvas = canvasRef.current
    const c = ctx()
    if (canvas && c) c.clearRect(0, 0, canvas.width, canvas.height)
    emptyRef.current = true
    setEmpty(true)
    onChange?.(null)
  }

  return (
    <div className={`flex flex-col gap-2 ${className}`}>
      <canvas
        ref={canvasRef}
        role="img"
        aria-label="Zone de signature — tracez avec la souris ou le doigt"
        style={{ height, touchAction: 'none' }}
        className="w-full cursor-crosshair rounded-xl border border-border bg-white"
        onPointerDown={start}
        onPointerMove={move}
        onPointerUp={end}
        onPointerLeave={end}
      />
      <div className="flex items-center gap-2">
        <Button type="button" size="sm" variant="outline" onClick={clear} disabled={empty}>
          <Eraser className="size-4" aria-hidden="true" /> Effacer
        </Button>
        {empty && (
          <span className="text-xs text-muted-foreground">
            Signature vide — tracez dans la zone ci-dessus.
          </span>
        )}
      </div>
    </div>
  )
}
