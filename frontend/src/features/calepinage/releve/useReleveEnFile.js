import { useCallback, useEffect, useRef, useState } from 'react'
import { mettreReleveEnFile, oublierReleveEnFile, rejouerReleve, releveEnAttente } from '../fileEnvoiPhotos'

/* ACAL1810 — le relevé de visite terminé HORS LIGNE : gardé dans la file des photos (même magasin, même rejeu), renvoyé
   seul au retour du réseau et à l'ouverture de l'écran. `onEnvoye(releve)` : le serveur l'a pris ; `onRefus(refus)` : il l'a
   refusé (message + champs). `enAttente` se lit dans la file : il survit au rechargement. */
export default function useReleveEnFile(calepinageId, { onEnvoye, onRefus }) {
  const [enAttente, setEnAttente] = useState(false)
  const rappels = useRef({ onEnvoye, onRefus })
  useEffect(() => { rappels.current = { onEnvoye, onRefus } })

  const renvoyer = useCallback(async () => {
    if (!calepinageId || (typeof navigator !== 'undefined' && navigator.onLine === false)) return
    const r = await rejouerReleve(calepinageId)
    setEnAttente(r.restantes > 0)
    if (r.envoye) rappels.current.onEnvoye?.(r.releve)
    if (r.refus) rappels.current.onRefus?.(r.refus)
  }, [calepinageId])

  useEffect(() => {
    if (!calepinageId) return undefined
    let vivant = true
    Promise.resolve(releveEnAttente(calepinageId)).then((oui) => { if (vivant) setEnAttente(!!oui) }).catch(() => {})
    Promise.resolve().then(renvoyer).catch(() => {})
    const auRetour = () => { Promise.resolve(renvoyer()).catch(() => {}) }
    window.addEventListener('online', auRetour)
    return () => { vivant = false; window.removeEventListener('online', auRetour) }
  }, [calepinageId, renvoyer])

  const garder = async (corps, releveId) => {
    await mettreReleveEnFile(calepinageId, { corps, releveId })
    setEnAttente(true)
  }
  const oublier = async () => {
    await oublierReleveEnFile(calepinageId)
    setEnAttente(false)
  }
  return { enAttente, garder, oublier }
}
