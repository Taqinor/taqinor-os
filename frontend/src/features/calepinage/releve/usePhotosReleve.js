import { useCallback, useEffect, useRef, useState } from 'react'
import calepinageApi from '../../../api/calepinageApi'
import { compterEnAttente, deposerOuMettreEnFile, genresEnAttente, rejouerFile } from '../fileEnvoiPhotos'
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

  /* Deux retours du réseau rapprochés (événement `online` + réouverture) ne rejouent pas la file deux fois : la même
     photo partait deux fois (mesuré sur la pile de revue, 24/11). */
  const rejeuEnCours = useRef(false)
  const envoyerLaFile = useCallback(() => {
    if (!calepinageId || (typeof navigator !== 'undefined' && navigator.onLine === false)) return
    if (rejeuEnCours.current) return
    rejeuEnCours.current = true
    Promise.resolve(rejouerFile(calepinageId)).finally(() => { rejeuEnCours.current = false }).then(async (r) => {
      setEnAttente(r?.restantes ?? 0)
      if (r?.envoyees) {
        // T4-X8-003 — les genres encore en file restent « en attente d'envoi » ; ceux partis passent « envoyée ».
        const restants = r.restantes ? await Promise.resolve(genresEnAttente(calepinageId)).catch(() => enFileRef.current) : []
        const partis = enFileRef.current.filter((g) => !(restants ?? []).includes(g))
        enFileRef.current = restants ?? []
        setGenresEnvoyes((e) => [...e, ...partis])
        setGenresEnFile(enFileRef.current)
        recharger()
      }
      if (r?.refusees?.length) setMessage(r.refusees[0].message || 'Une photo gardée a été refusée par le serveur.')
    }).catch(() => {})
  }, [calepinageId, recharger])

  useEffect(() => {
    if (!calepinageId) return undefined
    recharger()
    Promise.resolve(compterEnAttente(calepinageId)).then((n) => setEnAttente(n ?? 0)).catch(() => {})
    /* T4-X8-003 — après un rechargement, les photos gardées sont relues dans la file : chaque tuile dit « en attente
       d'envoi » et le compte les porte, jamais une tuile vide qui invite à reprendre la photo. */
    Promise.resolve(genresEnAttente(calepinageId)).then((genres) => {
      const enFile = [...new Set([...(genres ?? []), ...enFileRef.current])]
      enFileRef.current = enFile
      setGenresEnFile(enFile)
    }).catch(() => setMessage('Les photos gardées sur ce téléphone n’ont pas pu être relues.'))
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
