/* AOF79 — Fond de calque PDF : rastérisation de la page choisie, ZÉRO nouvelle
   dépendance et ZÉRO worker distant.
   ----------------------------------------------------------------------------
   `pdfjs-dist` est déjà installé et `features/ventes/PdfCanvas.jsx` en donne le
   patron : le worker est importé via le spécifieur Vite `?worker`, donc empaqueté
   et servi depuis NOTRE origine (jamais un CDN, qu'un bloqueur ou une CSP
   pourrait couper). On réutilise ce patron tel quel.

   Non-blocage : pdf.js analyse le document dans son worker (hors thread
   principal) et l'on ne peint QUE la page sélectionnée — un plan de 20 pages
   n'entraîne donc jamais 20 rendus. Le re-rendu haute résolution au zoom est
   déclenché par `doitRerasteriser` (jamais à chaque cran de molette).

   Mémoire : au démontage — et à chaque changement de fichier — le document
   pdf.js est détruit et le canvas peint est ramené à 0×0 (`libererFond`) ; un
   plan A0 laissé attaché pèse plusieurs dizaines de Mo. */
import { useCallback, useEffect, useRef, useState } from 'react'
import * as pdfjsLib from 'pdfjs-dist'
import PdfWorker from 'pdfjs-dist/build/pdf.worker.min.mjs?worker'
import {
  estPdf,
  messageFormatNonSupporte,
  ouvrirDocument,
  listerPages,
  rasteriserPage,
  facteurEchelle,
  doitRerasteriser,
  normaliserRotation,
  libererFond,
} from './rasteriserPdf'

// Un seul worker local partagé (le module ventes pose déjà le même) : on ne le
// remplace pas s'il est déjà en place, pour ne pas en fabriquer un second.
if (!pdfjsLib.GlobalWorkerOptions.workerPort) {
  pdfjsLib.GlobalWorkerOptions.workerPort = new PdfWorker()
}

export default function UnderlayPdf({
  fichier,
  zoom = 1,
  largeurDisponible = 900,
  onFond,
  onErreur,
}) {
  const hoteRef = useRef(null)
  const fondRef = useRef(null)
  const docRef = useRef(null)

  const [pages, setPages] = useState([])
  const [page, setPage] = useState(1)
  const [rotation, setRotation] = useState(0)
  const [opacite, setOpacite] = useState(0.55)
  const [verrouille, setVerrouille] = useState(true)
  const [etat, setEtat] = useState('vide') // vide | chargement | pret | erreur
  const [message, setMessage] = useState('')

  // ── Ouverture du document (worker pdf.js) ───────────────────────────────────
  useEffect(() => {
    if (!fichier) {
      setEtat('vide')
      return undefined
    }
    if (!estPdf(fichier)) {
      setEtat('erreur')
      setMessage(messageFormatNonSupporte(fichier))
      return undefined
    }
    let annule = false
    setEtat('chargement')
    setMessage('')

    const run = async () => {
      try {
        // Octets frais : pdf.js peut « détacher » le buffer transmis.
        const donnees = new Uint8Array(await fichier.arrayBuffer())
        const doc = await ouvrirDocument(pdfjsLib.getDocument, donnees)
        if (annule) {
          libererFond({ doc })
          return
        }
        docRef.current = doc
        setPages(listerPages(doc))
        setPage(1)
        setEtat('pret')
      } catch {
        if (annule) return
        setEtat('erreur')
        setMessage(
          "Ce PDF n'a pas pu être ouvert (fichier protégé ou endommagé). " +
            'Vous pouvez continuer au tracé, puis le remplacer plus tard.',
        )
        onErreur?.()
      }
    }
    run()

    return () => {
      annule = true
      libererFond({ doc: docRef.current, canvas: fondRef.current?.canvas })
      docRef.current = null
      fondRef.current = null
    }
  }, [fichier, onErreur])

  // ── Rastérisation de la page choisie (une seule à la fois) ──────────────────
  useEffect(() => {
    const doc = docRef.current
    const hote = hoteRef.current
    if (etat !== 'pret' || !doc || !hote) return undefined
    let annule = false

    const run = async () => {
      const premier = await doc.getPage(1)
      const base = premier.getViewport({ scale: 1, rotation: normaliserRotation(rotation) })
      const echelle = facteurEchelle({
        largeurDisponible,
        largeurPage: base.width,
        dpr: typeof window !== 'undefined' ? window.devicePixelRatio : 1,
        zoom,
      })
      const dejaRendu = fondRef.current
      const memePage = dejaRendu && dejaRendu.numeroPage === page
      const memeRotation = dejaRendu && dejaRendu.rotation === normaliserRotation(rotation)
      if (
        memePage &&
        memeRotation &&
        !doitRerasteriser({ echelleRendue: dejaRendu.echelle, echelleVoulue: echelle })
      ) {
        return // le canvas existant suffit : on ne repeint pas
      }

      const fond = await rasteriserPage(doc, {
        numeroPage: page,
        rotation,
        echelle,
        signalAnnule: () => annule,
      })
      if (annule || !fond) return
      // L'ancien canvas est relâché avant d'attacher le nouveau.
      if (fondRef.current?.canvas) libererFond({ canvas: fondRef.current.canvas })
      fondRef.current = fond
      hote.replaceChildren(fond.canvas)
      fond.canvas.className = 'ao-underlay-canvas'
      fond.canvas.style.width = '100%'
      fond.canvas.style.height = 'auto'
      onFond?.(fond)
    }
    run().catch(() => {
      if (!annule) {
        setEtat('erreur')
        setMessage("La page n'a pas pu être rendue. Essayez une autre page du plan.")
      }
    })

    return () => {
      annule = true
    }
  }, [etat, page, rotation, zoom, largeurDisponible, onFond])

  const tourner = useCallback(() => setRotation((r) => normaliserRotation(r + 90)), [])

  if (etat === 'erreur') {
    return (
      <div className="ao-underlay ao-underlay-erreur" role="alert" data-ao-underlay-erreur>
        <p>{message}</p>
      </div>
    )
  }

  return (
    <div className="ao-underlay" data-ao-underlay="pdf">
      <div className="ao-underlay-barre">
        <label htmlFor="ao-underlay-page">Page</label>
        <select
          id="ao-underlay-page"
          className="form-select"
          value={page}
          onChange={(e) => setPage(Number(e.target.value))}
          disabled={pages.length <= 1}
        >
          {pages.map((n) => (
            <option key={n} value={n}>
              {n} / {pages.length}
            </option>
          ))}
        </select>

        <button type="button" onClick={tourner} data-ao-underlay-rotation>
          Tourner 90° ({rotation}°)
        </button>

        <label htmlFor="ao-underlay-opacite">Opacité</label>
        <input
          id="ao-underlay-opacite"
          type="range"
          min="0"
          max="1"
          step="0.05"
          value={opacite}
          onChange={(e) => setOpacite(Number(e.target.value))}
        />

        <label className="ao-underlay-verrou" htmlFor="ao-underlay-verrou">
          <input
            id="ao-underlay-verrou"
            type="checkbox"
            checked={verrouille}
            onChange={(e) => setVerrouille(e.target.checked)}
          />
          <span>Calque verrouillé</span>
        </label>
      </div>

      {etat === 'chargement' && <p className="ao-hint">⏳ Ouverture du plan…</p>}

      <div
        className="ao-underlay-hote"
        ref={hoteRef}
        style={{ opacity: opacite, pointerEvents: verrouille ? 'none' : 'auto' }}
        aria-hidden="true"
      />
    </div>
  )
}
