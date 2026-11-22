import { createContext } from 'react'

/* Coque — le contexte des emplacements (`noeuds.surCarte`, `noeuds.panneau`, `noeuds.pied`,
   `noeuds.controle`, `prendrePied`, `tiroir`) que `CoqueAtelier` ouvre aux écrans d'étape (lus par
   `emplacements.jsx`). `tiroir` : le panneau d'étape est le TIROIR du bas (tablette, téléphone). */
export const ContexteCoque = createContext(null)

/* Coque — le MODE PRÉSENTATION (« Montrer au client », `/calepinage/:id/client`) : posé par
   `client/VueClient.jsx` autour de l'atelier. Valeur : `{ rendu(props) }` — l'habillage client que
   la coque rend autour de la 3D (`props` = `{ calepinageId, builderApi, noeudScene }`). Hors de
   cette route, `null` : l'atelier est inchangé. */
export const ContextePresentation = createContext(null)
