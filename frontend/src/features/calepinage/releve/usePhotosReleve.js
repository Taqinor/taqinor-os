import { useCallback, useEffect, useRef, useState } from 'react'
import calepinageApi from '../../../api/calepinageApi'
import { compterEnAttente, deposerOuMettreEnFile, rejouerFile } from '../fileEnvoiPhotos'
import { refusServeur } from '../commun/refusServeur'
import { dateDuJour } from './releveTelephone'

/* Les photos de site du calepinage pour l'écran téléphone : la liste servie (`GET photos/`),
   le dépôt par la file hors ligne EXISTANTE (ACAL892, même corps que l'onglet Photos), le
   rejeu au retour du réseau (comme `PhotoSiteCalage`) et le compte RÉEL de la file. */
export default function usePhotosReleve(calepinageId) {
  const [photos, setPhotos] = useState([])
  const [enAttente, setEnAttente] = useState(0)
  const [genresEnFile, setGenresEnFile] = useState([])
  /* T4-U4-021 — les genres ENVOYÉS par le rejeu mais pas encore relus dans la liste du serveur : ils restent comptés
     (« envoyée ») jusqu'à la relecture, jamais une tuile vidée et un compteur qui redescend pendant qu'elle se fait. */
  const [genresEnvoyes, setGenresEnvoyes] = useState([])
  const enFileRef = useRef([])
  const [enCours, setEnCours] = useState(null)
  const [message, setMessage] = useState(null)

  const recharger = useCallback(() => {
    if (!calepinageId) return
    Promise.resolve(calepinageApi.calepinages.photos?.(calepinageId))
      .then((res) => { setPhotos(res?.data?.photos ?? []); setGenresEnvoyes([]) })
      .catch(() => {})
  }, [calepinageId])

  const envoyerLaFile = useCallback(() => {
    if (!calepinageId || (typeof navigator !== 'undefined' && navigator.onLine === false)) return
    Promise.resolve(rejouerFile(calepinageId)).then((r) => {
      setEnAttente(r?.restantes ?? 0)
      if (r?.envoyees) {
        if (!r.restantes) {
          const partis = enFileRef.current
          enFileRef.current = []
          setGenresEnvoyes((e) => [...e, ...partis])
          setGenresEnFile([])
        }
        recharger()
      }
      if (r?.refusees?.length) setMessage(r.refusees[0].message || 'Une photo gardée a été refusée par le serveur.')
    }).catch(() => {})
  }, [calepinageId, recharger])

  useEffect(() => {
    if (!calepinageId) return undefined
    recharger()
    Promise.resolve(compterEnAttente(calepinageId)).then((n) => setEnAttente(n ?? 0)).catch(() => {})
    envoyerLaFile()
    window.addEventListener('online', envoyerLaFile)
    return () => window.removeEventListener('online', envoyerLaFile)
  }, [calepinageId, recharger, envoyerLaFile])

  /** Dépose (ou garde en file) UNE photo du genre donné ; rend l'id créé, sinon `null`. */
  const deposer = async (genre, fichier) => {
    if (!fichier || !calepinageId) return null
    setEnCours(genre)
    setMessage(null)
    try {
      const { enFile, res } = await deposerOuMettreEnFile(calepinageId, fichier, { genre, prise_le: dateDuJour() })
      if (enFile) {
        enFileRef.current = [...enFileRef.current, genre]
        setGenresEnFile(enFileRef.current)
        setEnAttente(await compterEnAttente(calepinageId))
        return null
      }
      recharger()
      return res?.data?.photo?.id ?? null
    } catch (err) {
      const { message: motif, champs } = refusServeur(err)
      const [champ, texte] = Object.entries(champs ?? {})[0] ?? []
      setMessage(texte ? `Photo refusée (${champ} : ${texte}).` : (motif || err?.message || 'La photo n’a pas pu être gardée.'))
      return null
    } finally {
      setEnCours(null)
    }
  }

  return { photos, enAttente, genresEnFile, genresEnvoyes, enCours, message, deposer, recharger }
}
