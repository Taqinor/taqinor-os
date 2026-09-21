/* AOF79 — Fond de calque IMAGE : glisser-déposer ou galerie/appareil mobile,
   avec correction d'orientation EXIF — sans aucune nouvelle dépendance.
   ----------------------------------------------------------------------------
   Une photo de plan prise au téléphone porte son orientation dans l'EXIF : sans
   correction, le plan arrive couché et toute la calibration part de travers.
   `createImageBitmap(blob, { imageOrientation: 'from-image' })` applique cette
   rotation NATIVEMENT (aucune bibliothèque EXIF à installer) ; les moteurs qui
   ne connaissent pas l'option retombent sur un `<img>` classique, que les
   navigateurs modernes redressent déjà (`image-orientation: from-image` est
   leur défaut).

   Mémoire : l'URL d'objet est révoquée et le canvas ramené à 0×0 au démontage
   comme au changement de fichier (`libererFond`). */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  estImageSupportee,
  messageFormatNonSupporte,
  normaliserRotation,
  libererFond,
} from './rasteriserPdf'

// Décode un blob image en source dessinable, EXIF redressé quand le moteur le
// sait faire. Renvoie { source, largeur, hauteur, url } — `url` (si posée) doit
// être révoquée par l'appelant.
async function decoderImage(blob) {
  if (typeof createImageBitmap === 'function') {
    try {
      const bitmap = await createImageBitmap(blob, { imageOrientation: 'from-image' })
      return { source: bitmap, largeur: bitmap.width, hauteur: bitmap.height, url: null }
    } catch {
      /* option inconnue de ce moteur → repli <img> ci-dessous */
    }
  }
  const url = URL.createObjectURL(blob)
  const img = new Image()
  img.src = url
  await img.decode()
  return { source: img, largeur: img.naturalWidth, hauteur: img.naturalHeight, url }
}

export default function UnderlayImage({ fichier, onFichier, onFond }) {
  const hoteRef = useRef(null)
  const fondRef = useRef(null)

  const [rotation, setRotation] = useState(0)
  const [opacite, setOpacite] = useState(0.55)
  const [verrouille, setVerrouille] = useState(true)
  const [survol, setSurvol] = useState(false)
  const [erreur, setErreur] = useState('')

  const accepter = useCallback(
    (f) => {
      if (!f) return
      if (!estImageSupportee(f)) {
        setErreur(messageFormatNonSupporte(f))
        return
      }
      setErreur('')
      onFichier?.(f)
    },
    [onFichier],
  )

  // Format non supporté : dérivé directement du fichier reçu, jamais posé en
  // state depuis l'effet (le refus n'a pas besoin d'attendre un rendu de plus).
  const erreurFormat = useMemo(
    () => (fichier && !estImageSupportee(fichier) ? messageFormatNonSupporte(fichier) : ''),
    [fichier],
  )

  useEffect(() => {
    const hote = hoteRef.current
    if (!fichier || !hote || !estImageSupportee(fichier)) return undefined
    let annule = false

    const run = async () => {
      const { source, largeur, hauteur, url } = await decoderImage(fichier)
      if (annule) {
        if (url) URL.revokeObjectURL(url)
        return
      }
      const rot = normaliserRotation(rotation)
      const quart = rot % 180 !== 0
      const canvas = document.createElement('canvas')
      canvas.className = 'ao-underlay-canvas'
      canvas.width = quart ? hauteur : largeur
      canvas.height = quart ? largeur : hauteur
      const ctx = canvas.getContext('2d')
      ctx.translate(canvas.width / 2, canvas.height / 2)
      ctx.rotate((rot * Math.PI) / 180)
      ctx.drawImage(source, -largeur / 2, -hauteur / 2)
      if (annule) {
        if (url) URL.revokeObjectURL(url)
        return
      }
      if (fondRef.current) libererFond(fondRef.current)
      const fond = {
        canvas,
        url,
        rotation: rot,
        echelle: 1,
        largeurPx: canvas.width,
        hauteurPx: canvas.height,
      }
      fondRef.current = fond
      canvas.style.width = '100%'
      canvas.style.height = 'auto'
      hote.replaceChildren(canvas)
      onFond?.(fond)
    }
    run().catch(() => {
      if (!annule) setErreur("Cette image n'a pas pu être ouverte. Essayez un autre fichier.")
    })

    return () => {
      annule = true
      libererFond(fondRef.current)
      fondRef.current = null
    }
  }, [fichier, rotation, onFond])

  return (
    <div className="ao-underlay" data-ao-underlay="image">
      <div
        className={`ao-underlay-depot${survol ? ' est-survole' : ''}`}
        onDragOver={(e) => {
          e.preventDefault()
          setSurvol(true)
        }}
        onDragLeave={() => setSurvol(false)}
        onDrop={(e) => {
          e.preventDefault()
          setSurvol(false)
          accepter(e.dataTransfer?.files?.[0])
        }}
      >
        <p>Glissez une photo ou un scan du plan ici.</p>
        <label className="ao-underlay-galerie" htmlFor="ao-underlay-fichier">
          <span>Choisir depuis la galerie ou l&apos;appareil photo</span>
          <input
            id="ao-underlay-fichier"
            type="file"
            accept="image/*"
            capture="environment"
            onChange={(e) => accepter(e.target.files?.[0])}
          />
        </label>
      </div>

      {(erreurFormat || erreur) && (
        <p role="alert" className="ao-underlay-erreur" data-ao-underlay-erreur>
          {erreurFormat || erreur}
        </p>
      )}

      <div className="ao-underlay-barre">
        <button
          type="button"
          onClick={() => setRotation((r) => normaliserRotation(r + 90))}
          data-ao-underlay-rotation
        >
          Tourner 90° ({rotation}°)
        </button>
        <label htmlFor="ao-underlay-img-opacite">Opacité</label>
        <input
          id="ao-underlay-img-opacite"
          type="range"
          min="0"
          max="1"
          step="0.05"
          value={opacite}
          onChange={(e) => setOpacite(Number(e.target.value))}
        />
        <label className="ao-underlay-verrou" htmlFor="ao-underlay-img-verrou">
          <input
            id="ao-underlay-img-verrou"
            type="checkbox"
            checked={verrouille}
            onChange={(e) => setVerrouille(e.target.checked)}
          />
          <span>Calque verrouillé</span>
        </label>
      </div>

      <div
        className="ao-underlay-hote"
        ref={hoteRef}
        style={{ opacity: opacite, pointerEvents: verrouille ? 'none' : 'auto' }}
        aria-hidden="true"
      />
    </div>
  )
}
