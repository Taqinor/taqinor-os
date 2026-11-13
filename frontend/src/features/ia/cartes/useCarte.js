// COP-F2/F3 — crochets partagés par les cartes de l'assistant.
import { useCallback, useState } from 'react'
import { useDispatch } from 'react-redux'
import iaApi from '../../../api/iaApi'
import { ajouterMessageLocal, majCarte } from '../store/iaSlice'
import { messageLocal } from './cartes'

/** Écrit dans l'état d'UNE carte (rangée dans le store : le tiroir est remonté
 *  à chaque changement de module). Sans index (carte imbriquée) : sans effet. */
export function usePatchCarte(index, carteIdx) {
  const dispatch = useDispatch()
  return useCallback((patch) => {
    if (index == null || carteIdx == null) return
    dispatch(majCarte({ index, carte: carteIdx, patch }))
  }, [dispatch, index, carteIdx])
}

/** La carte « touche » d'une touche lue par `GET crm/assistant/touches/<id>/`. */
export function carteToucheDe(donnees) {
  return {
    type: 'resultat', action_key: 'crm.suivi.preparer_touche',
    libelle: 'Préparer une touche', carte: 'touche', donnees,
  }
}

/** « Préparer » : appel DIRECT à Django (zéro question au modèle), la carte
 *  « touche » s'ajoute à la conversation comme une carte locale. */
export function usePreparerTouche() {
  const dispatch = useDispatch()
  const [occupe, setOccupe] = useState(null)
  const [erreur, setErreur] = useState('')
  const preparer = useCallback(async (toucheId) => {
    setOccupe(toucheId)
    setErreur('')
    try {
      const res = await iaApi.getToucheAssistant(toucheId)
      dispatch(ajouterMessageLocal(messageLocal([carteToucheDe(res.data)])))
      return true
    } catch {
      setErreur('Impossible de préparer cette touche pour le moment.')
      return false
    } finally {
      setOccupe(null)
    }
  }, [dispatch])
  return { preparer, occupe, erreur }
}
