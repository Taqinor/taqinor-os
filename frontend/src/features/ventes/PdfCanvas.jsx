/* Rendu de l'aperçu devis avec PDF.js (canvas) — INBLOCABLE.
   On ne pointe PLUS un <iframe>/<embed> vers le PDF (ça, un bloqueur de pub ou
   la politique PDF de Chrome peut le bloquer). À la place, on dessine le PDF
   page par page sur des <canvas> à partir des MÊMES octets authentifiés que le
   téléchargement. Aucun bloqueur ne peut empêcher un canvas de s'afficher.

   Le worker PDF.js est importé via `?worker` : Vite l'empaquette et le sert
   depuis NOTRE origine (jamais un CDN blocable), avec le bon type MIME. */
import { useEffect, useRef, useState } from 'react'
import * as pdfjsLib from 'pdfjs-dist'
import PdfWorker from 'pdfjs-dist/build/pdf.worker.min.mjs?worker'

// Un seul worker, servi localement, réutilisé pour tous les rendus.
pdfjsLib.GlobalWorkerOptions.workerPort = new PdfWorker()

export default function PdfCanvas({ blob, onError }) {
  const pagesRef = useRef(null)
  const [rendering, setRendering] = useState(true)

  useEffect(() => {
    if (!blob) return undefined
    let cancelled = false
    let pdf = null
    const host = pagesRef.current
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setRendering(true)

    const run = async () => {
      try {
        // Octets frais (PDF.js peut « détacher » le buffer ; le blob d'origine,
        // gardé par le panneau, reste intact pour le téléchargement).
        const data = new Uint8Array(await blob.arrayBuffer())
        pdf = await pdfjsLib.getDocument({ data }).promise
        if (cancelled || !host) return
        host.replaceChildren() // vide un éventuel rendu précédent

        const dpr = Math.min(window.devicePixelRatio || 1, 2) // netteté high-DPI
        const avail = (host.clientWidth || 800) - 24 // marge interne
        const cssWidth = Math.max(280, Math.min(avail, 900)) // lisible, borné

        for (let n = 1; n <= pdf.numPages; n += 1) {
          const page = await pdf.getPage(n)
          if (cancelled) return
          const base = page.getViewport({ scale: 1 })
          const scale = (cssWidth / base.width) * dpr
          const vp = page.getViewport({ scale })
          const canvas = document.createElement('canvas')
          canvas.className = 'ldp-pdf-page'
          canvas.width = Math.floor(vp.width)
          canvas.height = Math.floor(vp.height)
          canvas.style.width = `${cssWidth}px`
          canvas.style.height = `${Math.floor(vp.height / dpr)}px`
          host.appendChild(canvas)
          await page.render({ canvasContext: canvas.getContext('2d'), viewport: vp }).promise
          if (cancelled) return
        }
        if (!cancelled) setRendering(false)
      } catch (err) {
        if (!cancelled) onError?.(err)
      }
    }
    run()

    return () => {
      cancelled = true
      if (pdf) { try { pdf.destroy() } catch { /* ignore */ } }
    }
  }, [blob, onError])

  return (
    <div className="ldp-pdfjs-wrap" tabIndex={0} role="region" aria-label="Aperçu du PDF (défilement au clavier)">
      {rendering && (
        <p className="gen-hint ldp-pdf-loading">⏳ Rendu de l'aperçu…</p>
      )}
      <div className="ldp-pdfjs" ref={pagesRef} />
    </div>
  )
}
