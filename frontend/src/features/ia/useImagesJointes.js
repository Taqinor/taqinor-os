// COP2-W2 — les images jointes à la question en cours de saisie (capture d'un message de client).
//
// L'état vit dans le COMPOSANT (jamais dans Redux) : une image réduite pèse plusieurs centaines de Ko de
// base64, qui ne doivent ni entrer dans le magasin ni dans l'historique conservé. Le magasin ne garde que le
// NOMBRE d'images d'un message envoyé (`images_jointes`). Les URL d'objet des miniatures sont révoquées dès
// qu'une image est retirée, que la question part, ou que l'écran disparaît.
import { useCallback, useEffect, useRef, useState } from 'react'
import { reduireImage, fichierImageOk } from './images'
import { IMAGES_MAX } from './copilotMessages'

export const MESSAGE_SEULEMENT_IMAGES = 'Seules les images sont acceptées.'
export const MESSAGE_IMAGES_MAX = `${IMAGES_MAX} images au maximum.`
export const MESSAGE_IMAGE_ILLISIBLE = 'Image illisible ou trop lourde : essayez une autre capture.'

const revoquer = (images) => images.forEach((im) => URL.revokeObjectURL(im.apercu))

let compteur = 0

export default function useImagesJointes({ acceptees = false } = {}) {
  const [images, setImages] = useState([])
  const [erreur, setErreur] = useState('')
  const [occupe, setOccupe] = useState(false)
  const courantes = useRef([])
  const enCours = useRef(0)

  useEffect(() => { courantes.current = images }, [images])
  // Démontage : plus aucune URL d'objet ne reste vivante.
  useEffect(() => () => revoquer(courantes.current), [])

  const ajouter = useCallback(async (fichiers) => {
    if (!acceptees) return
    const liste = Array.from(fichiers ?? [])
    if (liste.length === 0) return
    const images_ok = liste.filter(fichierImageOk)
    let message = images_ok.length < liste.length ? MESSAGE_SEULEMENT_IMAGES : ''
    const places = Math.max(0, IMAGES_MAX - courantes.current.length - enCours.current)
    if (images_ok.length > places) message = MESSAGE_IMAGES_MAX
    const retenus = images_ok.slice(0, places)
    setErreur(message)
    if (retenus.length === 0) return
    enCours.current += retenus.length
    setOccupe(true)
    try {
      for (const fichier of retenus) {
        try {
          const reduite = await reduireImage(fichier)
          compteur += 1
          const image = { id: `img-${compteur}`, ...reduite } // l'identifiant est figé ICI, pas dans la mise à jour différée
          setImages((prev) => [...prev, image])
        } catch {
          setErreur(MESSAGE_IMAGE_ILLISIBLE)
        } finally {
          enCours.current -= 1
        }
      }
    } finally {
      setOccupe(enCours.current > 0)
    }
  }, [acceptees])

  const retirer = useCallback((id) => {
    revoquer(courantes.current.filter((im) => im.id === id))
    setImages((prev) => prev.filter((im) => im.id !== id))
    setErreur('')
  }, [])

  // La question est partie : les miniatures disparaissent, leurs URL aussi.
  const vider = useCallback(() => {
    revoquer(courantes.current)
    setImages([])
    setErreur('')
  }, [])

  return { acceptees, images, erreur, occupe, ajouter, retirer, vider }
}
