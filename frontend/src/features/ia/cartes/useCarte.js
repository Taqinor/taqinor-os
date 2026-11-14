// COP-F2/F3 — crochets partagés par les cartes de l'assistant.
import { useCallback, useState } from 'react'
import { useDispatch } from 'react-redux'
import { useNavigate } from 'react-router-dom'
import iaApi from '../../../api/iaApi'
import { ajouterMessageLocal, closeCopilot, majCarte, majCartesTouche } from '../store/iaSlice'
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

/** Une carte qui OUVRE un écran (« Ouvrir la fiche », « Ouvrir la visite », le
 *  lead d'une touche) : la navigation se fait ET le tiroir du Copilote se referme
 *  — il est modal, et sur un téléphone il couvre toute la page : sans cela
 *  l'appui ne montrait rien. Sur la page de l'assistant, fermer est sans effet. */
export function useOuvrirEcran() {
  const navigate = useNavigate()
  const dispatch = useDispatch()
  return useCallback((...args) => {
    navigate(...args)
    dispatch(closeCopilot())
  }, [navigate, dispatch])
}

/** Écrit dans TOUTES les cartes « touche » de la conversation qui portent la
 *  touche `toucheId` (une réponse enregistrée vaut pour chacune d'elles). */
export function useMajCartesTouche() {
  const dispatch = useDispatch()
  return useCallback((toucheId, patch) => {
    dispatch(majCartesTouche({ toucheId, patch }))
  }, [dispatch])
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
