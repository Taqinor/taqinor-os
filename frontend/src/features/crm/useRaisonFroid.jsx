// ERR-ACVI9-KANBAN-FROID — la question « pourquoi au Froid ? » des gestes
// unitaires (glisser du kanban, sélecteur de la liste, menu d'étape de la fiche) :
// même forme que `useConfirmerRecul`, une promesse. Elle rend le code choisi, ou
// `null` si l'utilisateur annule (l'appelant n'écrit alors RIEN). Le serveur reste
// seul juge (`parquer_lead`) : son refus est affiché par l'appelant.
import { useCallback, useRef, useState } from 'react'
import RaisonFroidDialog from './RaisonFroidDialog'

export function useRaisonFroid() {
  const [lead, setLead] = useState(null)
  const fin = useRef(null)
  const demander = useCallback((fiche) => new Promise((resolve) => {
    fin.current = resolve
    setLead(fiche)
  }), [])
  const finir = useCallback((raison) => {
    setLead(null)
    fin.current?.(raison)
    fin.current = null
  }, [])
  return {
    demanderRaisonFroid: demander,
    dialogueRaisonFroid: lead ? <RaisonFroidDialog lead={lead} onFin={finir} /> : null,
  }
}
