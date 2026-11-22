import { createContext } from 'react'

/* Coque — le contexte des emplacements (`noeuds.surCarte`, `noeuds.panneau`, `noeuds.pied`,
   `prendrePied`) que `CoqueAtelier` ouvre aux écrans d'étape (lus par `emplacements.jsx`). */
export const ContexteCoque = createContext(null)
