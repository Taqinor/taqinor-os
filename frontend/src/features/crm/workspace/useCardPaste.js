import { useState } from 'react'
import { parsePasteCard } from '../../../hooks/usePasteClean'

// QJR638 — collage d'une carte de visite dans « Nom » (VX237) : { nom,
// telephone } détectés, JAMAIS répartis en silence — l'écran affiche une
// bannière et n'applique qu'après confirmation (`applyCardPaste`).
// `appliquer({ nom, telephone })` écrit dans l'état du formulaire appelant.
export default function useCardPaste(appliquer) {
  const [cardPaste, setCardPaste] = useState(null)
  const onNomPaste = (e) => {
    const card = parsePasteCard(e.clipboardData?.getData('text'))
    if (card) setCardPaste(card)
  }
  const applyCardPaste = () => {
    if (!cardPaste) return
    appliquer({ nom: cardPaste.nom, telephone: cardPaste.telephone })
    setCardPaste(null)
  }
  const annuler = () => setCardPaste(null)
  return { cardPaste, onNomPaste, applyCardPaste, annuler }
}
