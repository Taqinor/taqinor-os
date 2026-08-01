import { useCallback, useEffect, useRef, useState } from 'react'
import * as pdfjsLib from 'pdfjs-dist'
import { AlertTriangle, FileText, GitCompare, Loader2, Minus, Plus, Square, X } from 'lucide-react'
import { Button, EmptyState } from '../../../ui'

/* ============================================================================
   AOF175 — Prévisualisation d'une pièce + comparaison de versions.
   ----------------------------------------------------------------------------
   **AUCUN `<iframe>` NI `<embed>`.** Le dépôt l'interdit et fournit déjà le
   patron : `features/ventes/PdfCanvas.jsx` dessine le PDF sur un `<canvas>` à
   partir des MÊMES octets authentifiés, ce qu'aucun bloqueur ne peut empêcher.
   Ce composant reprend exactement ce patron et lui ajoute ce dont une PLANCHE
   A3 a besoin et qu'un aperçu de devis n'a pas : zoom continu, panoramique à
   la souris, plein écran, et un mode « comparer à la version précédente »
   côte à côte — c'est ce mode-là qui rend VISIBLE qu'un indice de révision a
   bougé (le défaut n°1 de la session : le fichier frère périmé).

   **UN SEUL WORKER pdfjs pour toute l'application.** `GlobalWorkerOptions` est
   un SINGLETON de la bibliothèque : le premier module qui pose le port gagne,
   tous les autres le réutilisent. `ensureWorkerPartage()` ci-dessous n'ouvre
   donc un worker QUE si personne (underlay de calepinage, `PdfCanvas`) ne l'a
   déjà fait, et mémoïse sa promesse — deux volets côte à côte en mode
   comparaison n'en ouvrent pas deux. L'import du worker est DYNAMIQUE et
   n'est évalué que dans ce cas : rien à charger quand le port existe déjà.

   **Zéro fuite au démontage** : chaque rendu annule son tour de boucle
   (`cancelled`), `pdf.destroy()` libère le document, et l'hôte est vidé par
   `replaceChildren()` avant tout nouveau rendu.
   ========================================================================== */

// Promesse mémoïsée : un worker au plus pour toute la durée de vie de l'onglet.
let workerPromise = null

/** Garantit UN worker pdfjs partagé. Renvoie `true` si CE module l'a posé,
    `false` s'il était déjà posé ailleurs (cas nominal quand l'underlay ou
    `PdfCanvas` a été monté avant). Servi depuis NOTRE origine (Vite `?worker`),
    jamais un CDN blocable. */
export function ensureWorkerPartage(lib = pdfjsLib) {
  const opts = lib.GlobalWorkerOptions
  if (opts.workerPort || opts.workerSrc) return Promise.resolve(false)
  if (!workerPromise) {
    workerPromise = import('pdfjs-dist/build/pdf.worker.min.mjs?worker')
      .then(({ default: PdfWorker }) => {
        if (!opts.workerPort && !opts.workerSrc) opts.workerPort = new PdfWorker()
        return true
      })
  }
  return workerPromise
}

const ZOOM_MIN = 0.5
const ZOOM_MAX = 4
const ZOOM_STEP = 0.25

const clampZoom = (z) => Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, Math.round(z * 100) / 100))

/* Un volet de rendu : un document PDF, dessiné page par page sur des canvas.
   `blob` peut être un Blob ou un ArrayBuffer/Uint8Array — on ne fait que lire
   ses octets. */
function PdfVolet({ blob, zoom, label, onError }) {
  const hostRef = useRef(null)
  const [rendering, setRendering] = useState(true)
  const [failed, setFailed] = useState(null)

  useEffect(() => {
    if (!blob) return undefined
    let cancelled = false
    let pdf = null
    const host = hostRef.current
    setRendering(true)
    setFailed(null)

    const run = async () => {
      try {
        await ensureWorkerPartage()
        if (cancelled) return
        // Octets frais : pdfjs peut « détacher » le buffer, le blob d'origine
        // reste intact pour un second rendu (zoom, comparaison).
        const bytes = typeof blob.arrayBuffer === 'function'
          ? new Uint8Array(await blob.arrayBuffer())
          : new Uint8Array(blob)
        pdf = await pdfjsLib.getDocument({ data: bytes }).promise
        if (cancelled || !host) return
        host.replaceChildren()

        const dpr = Math.min(globalThis.devicePixelRatio || 1, 2)
        const dispo = (host.clientWidth || 900) - 8
        // Une planche A3 doit rester lisible AU TRAIT : la largeur de base
        // n'est pas bornée par le haut comme pour un devis A4 — c'est le zoom
        // qui commande, et le conteneur défile.
        const cssWidth = Math.max(280, dispo) * zoom

        for (let n = 1; n <= pdf.numPages; n += 1) {
          const page = await pdf.getPage(n)
          if (cancelled) return
          const base = page.getViewport({ scale: 1 })
          const scale = (cssWidth / base.width) * dpr
          const vp = page.getViewport({ scale })
          const canvas = document.createElement('canvas')
          canvas.className = 'block max-w-none rounded-sm bg-white shadow-sm'
          canvas.width = Math.floor(vp.width)
          canvas.height = Math.floor(vp.height)
          canvas.style.width = `${Math.floor(cssWidth)}px`
          canvas.style.height = `${Math.floor(vp.height / dpr)}px`
          host.appendChild(canvas)
          await page.render({ canvasContext: canvas.getContext('2d'), viewport: vp }).promise
          if (cancelled) return
        }
        if (!cancelled) setRendering(false)
      } catch (err) {
        if (cancelled) return
        setRendering(false)
        setFailed(err?.message || 'Rendu impossible.')
        onError?.(err)
      }
    }
    run()

    return () => {
      cancelled = true
      if (host) host.replaceChildren()
      if (pdf) { try { pdf.destroy() } catch { /* déjà détruit */ } }
    }
  }, [blob, zoom, onError])

  return (
    <div className="flex min-w-0 flex-1 flex-col gap-1">
      {label && <p className="text-xs font-medium text-muted-foreground">{label}</p>}
      {rendering && (
        <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
          Rendu de l’aperçu…
        </p>
      )}
      {failed && (
        <p className="flex items-center gap-1.5 text-xs text-destructive">
          <AlertTriangle className="size-3.5" aria-hidden="true" />
          {failed}
        </p>
      )}
      <div ref={hostRef} data-testid="pdf-volet" className="flex flex-col gap-2" />
    </div>
  )
}

export default function PiecePreview({
  piece,
  blob,
  blobPrecedent,
  onError,
}) {
  const [zoom, setZoom] = useState(1)
  const [plein, setPlein] = useState(false)
  const [comparer, setComparer] = useState(false)
  const scrollRef = useRef(null)
  const panRef = useRef(null)

  // Panoramique à la souris (planche A3 : le déplacement au glisser est le
  // geste naturel, la barre de défilement ne suffit pas).
  const onPointerDown = useCallback((e) => {
    const el = scrollRef.current
    if (!el) return
    panRef.current = { x: e.clientX, y: e.clientY, left: el.scrollLeft, top: el.scrollTop }
  }, [])
  const onPointerMove = useCallback((e) => {
    const el = scrollRef.current
    const start = panRef.current
    if (!el || !start) return
    el.scrollLeft = start.left - (e.clientX - start.x)
    el.scrollTop = start.top - (e.clientY - start.y)
  }, [])
  const endPan = useCallback(() => { panRef.current = null }, [])

  // Échap quitte le plein écran (jamais une souricière).
  useEffect(() => {
    if (!plein) return undefined
    const onKey = (e) => { if (e.key === 'Escape') setPlein(false) }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [plein])

  if (!piece) {
    return (
      <EmptyState
        icon={FileText}
        title="Aucune pièce sélectionnée"
        description="Sélectionnez une pièce du dossier pour l’afficher."
      />
    )
  }
  if (!blob) {
    return (
      <EmptyState
        icon={FileText}
        title={piece.libelle || piece.code}
        description="Cette pièce n’a pas encore d’aperçu — générez-la pour la lire."
      />
    )
  }

  const titre = piece.libelle || piece.code
  const indice = piece.indice_revision
  const indicePrecedent = piece.indice_revision_precedent
  const comparaisonPossible = Boolean(blobPrecedent)

  return (
    <div
      className={plein
        ? 'fixed inset-0 z-50 flex flex-col gap-2 bg-background p-3'
        : 'flex flex-col gap-2'}
      role={plein ? 'dialog' : undefined}
      aria-modal={plein ? 'true' : undefined}
      aria-label={plein ? `Aperçu plein écran — ${titre}` : undefined}
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-medium">{titre}</span>
        {indice && <span className="text-xs text-muted-foreground">Indice {indice}</span>}
        <div className="ml-auto flex items-center gap-1">
          <Button
            size="icon-sm" variant="outline" aria-label="Dézoomer"
            disabled={zoom <= ZOOM_MIN}
            onClick={() => setZoom((z) => clampZoom(z - ZOOM_STEP))}
          >
            <Minus aria-hidden="true" />
          </Button>
          <span className="min-w-12 text-center text-xs tabular-nums" aria-live="polite">
            {Math.round(zoom * 100)} %
          </span>
          <Button
            size="icon-sm" variant="outline" aria-label="Zoomer"
            disabled={zoom >= ZOOM_MAX}
            onClick={() => setZoom((z) => clampZoom(z + ZOOM_STEP))}
          >
            <Plus aria-hidden="true" />
          </Button>
          <Button
            size="sm" variant="outline"
            disabled={!comparaisonPossible}
            aria-pressed={comparer}
            onClick={() => setComparer((c) => !c)}
          >
            <GitCompare aria-hidden="true" />
            {comparer ? 'Version courante seule' : 'Comparer à la version précédente'}
          </Button>
          <Button
            size="sm" variant="outline"
            onClick={() => setPlein((p) => !p)}
          >
            {plein ? <X aria-hidden="true" /> : <Square aria-hidden="true" />}
            {plein ? 'Quitter le plein écran' : 'Plein écran'}
          </Button>
        </div>
      </div>

      <div
        ref={scrollRef}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={endPan}
        onPointerLeave={endPan}
        tabIndex={0}
        role="region"
        aria-label={`Aperçu de « ${titre} » (défilement au clavier, panoramique au glisser)`}
        className={`flex gap-3 overflow-auto rounded-md border border-border bg-muted/30 p-2 ${
          plein ? 'flex-1' : 'max-h-[32rem]'
        }`}
      >
        {comparer && comparaisonPossible && (
          <PdfVolet
            blob={blobPrecedent}
            zoom={zoom}
            label={indicePrecedent ? `Version précédente — indice ${indicePrecedent}` : 'Version précédente'}
            onError={onError}
          />
        )}
        <PdfVolet
          blob={blob}
          zoom={zoom}
          label={comparer ? (indice ? `Version courante — indice ${indice}` : 'Version courante') : null}
          onError={onError}
        />
      </div>
    </div>
  )
}
