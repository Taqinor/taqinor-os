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
/** R2-040 — émis par la fiche après chaque écriture réussie et à sa fermeture : `detail = { tache }` (la tâche
 *  rendue par le serveur, ou `null` quand la fiche n'a rien de plus frais que l'identifiant). */
export const EVENEMENT_ECRITE = 'taqinor:taches:ecrite'
export const MARQUE_FICHE = 'tchFiche'

/** R2-040 — la fiche est montée par la coquille, pas par l'écran : elle prévient l'écran qu'une tâche a changé. */
export function signalerEcrite(tache = null) {
  if (typeof window === 'undefined') return
  window.dispatchEvent(new CustomEvent(EVENEMENT_ECRITE, { detail: { tache } }))
}

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

/** Appelle `rappel(detail)` après chaque création (saisie, collage, file rejouée) ET (R2-040) après chaque écriture
 *  de la fiche (Fait, Supprimer, Quand… : `{ tache }`) — l'écran se met à jour seul, sans rechargement. */
export function useApresCreation(rappel) {
  useEffect(() => {
    const surEvenement = (e) => rappel(e?.detail ?? {})
    window.addEventListener(EVENEMENT_CREEES, surEvenement)
    window.addEventListener(EVENEMENT_ECRITE, surEvenement)
    return () => {
      window.removeEventListener(EVENEMENT_CREEES, surEvenement)
      window.removeEventListener(EVENEMENT_ECRITE, surEvenement)
    }
  }, [rappel])
}
