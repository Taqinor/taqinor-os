// Soumission commune des dialogues de l'onglet Contrats : garde « en cours » et
// le refus du serveur (son `detail`, affiché en place).
import { useState } from 'react'
import { detailErreur } from './outils'

/** `soumettre(appel)` : lance l'appel, rend true si réussi, sinon pose le detail du serveur. */
export function useSoumission() {
  const [occupe, setOccupe] = useState(false)
  const [erreur, setErreur] = useState('')
  const soumettre = async (appel) => {
    setOccupe(true)
    setErreur('')
    try {
      await appel()
      return true
    } catch (err) {
      setErreur(await detailErreur(err))
      return false
    } finally {
      setOccupe(false)
    }
  }
  return { occupe, erreur, setErreur, soumettre }
}
