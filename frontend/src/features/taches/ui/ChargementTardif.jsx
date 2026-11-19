import { useEffect, useState } from 'react'

import SqueletteListe, { LigneOs } from './SqueletteListe'

/* ============================================================================
   Raccord F2 — l'état « chargement » commun aux écrans de Tâches (spec-7 « Partout » : squelette, jamais sur une liste
   déjà affichée ; textes.md §2.19 : annonce « Chargement »). L'écran le monte tant qu'il n'a RIEN à montrer.
   R4-42 — la classe est `squelette-liste` : `.squelette` est le bloc d'UNE barre de 44 px de saisie.css (fiche, bilan) ; sous elle ce
   squelette de liste tenait dans 44 px de haut et la page se posait PAR-DESSUS (Projets n'affichait que « Nouveau projet »).
   R2-089 — dès 300 ms (une réponse rapide ne fait rien clignoter ; au-delà, l'écran montre déjà SA forme) : deux
   sections de lignes de tâches « os », comme etat-chargement.html — jamais le squelette des tableaux de bord de l'ERP.
   ========================================================================== */

const DELAI_MS = 300

/** Re-export : les lignes d'Aujourd'hui et de Proposé la lisent d'ici depuis toujours. */
export { LigneOs }

export default function ChargementTardif({ actif = true }) {
  const [visible, setVisible] = useState(false)
  useEffect(() => {
    if (!actif) return undefined
    const minuteur = setTimeout(() => setVisible(true), DELAI_MS)
    return () => { clearTimeout(minuteur); setVisible(false) }
  }, [actif])
  if (!actif || !visible) return null
  return <SqueletteListe />
}
