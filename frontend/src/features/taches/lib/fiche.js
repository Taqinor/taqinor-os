import { useCallback, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'

/* ============================================================================
   Raccord F2 — les écrans se parlent : une SEULE façon d'ouvrir la fiche d'une tâche (`?tache=<id>`, la coquille
   la monte) et une SEULE façon d'écouter « des tâches viennent d'être créées » (`taqinor:taches:creees`, émis par
   la feuille de saisie). La fiche s'ouvre en AJOUTANT une entrée d'historique marquée : le retour arrière du
   navigateur la ferme sans quitter l'écran, et la coquille la ferme par ce même retour (le focus revient à la
   ligne qui l'a ouverte, FeuilleACrans s'en charge). Ouverte par un lien direct (notification de rappel), sans
   marque, elle se ferme en retirant le paramètre.
   ========================================================================== */

export const EVENEMENT_CREEES = 'taqinor:taches:creees'
export const MARQUE_FICHE = 'tchFiche'

/** `(id) => void` : ouvre la fiche de la tâche `id` sur l'écran courant. */
export function useOuvrirFiche() {
  const [, setParams] = useSearchParams()
  return useCallback((id) => {
    setParams((actuels) => {
      const suite = new URLSearchParams(actuels)
      suite.set('tache', String(id))
      return suite
    }, { state: { [MARQUE_FICHE]: true } })
  }, [setParams])
}

/** Appelle `rappel(detail)` après chaque création (saisie, collage, file rejouée) — l'écran se met à jour seul. */
export function useApresCreation(rappel) {
  useEffect(() => {
    const surCreees = (e) => rappel(e?.detail ?? {})
    window.addEventListener(EVENEMENT_CREEES, surCreees)
    return () => window.removeEventListener(EVENEMENT_CREEES, surCreees)
  }, [rappel])
}
