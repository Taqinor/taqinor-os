// Lit l'acte (détail + contenu) pour préremplir un dialogue : nom du client,
// lieu. Le refus du serveur est rendu tel quel dans `erreur`.
import { useEffect, useState } from 'react'
import documentsApi from '../../../api/documentsApi'
import { detailErreur } from './outils'

export default function useActeContenu(acteId, actif = true) {
  const [acte, setActe] = useState(null)
  const [erreur, setErreur] = useState('')
  useEffect(() => {
    if (!actif || !acteId) return undefined
    let annule = false
    documentsApi.acte(acteId)
      .then((res) => { if (!annule) setActe(res.data) })
      .catch(async (err) => {
        const detail = await detailErreur(err)
        if (!annule) setErreur(detail)
      })
    return () => { annule = true }
  }, [acteId, actif])
  return { acte, erreur }
}
