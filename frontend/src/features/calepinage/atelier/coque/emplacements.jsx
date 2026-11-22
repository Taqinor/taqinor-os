import { useContext, useEffect } from 'react'
import { createPortal } from 'react-dom'
import { ongletParCle } from '../onglets'
import { ContexteCoque } from './contexteCoque'

/* ============================================================================
   COQUE — LES EMPLACEMENTS QU'UN ÉCRAN D'ÉTAPE PEUT REMPLIR.
   ----------------------------------------------------------------------------
   Un écran d'étape est monté DANS le panneau de droite (cadre `carte`) ou au
   centre (cadres `plein` / `plein-panneau`). Il atteint les autres zones de la
   coque par trois portails, sans connaître la coque :
     - <SurCarte>     : un calque posé SUR la carte (puces, barre d'outils
                        flottante) ; hors coque, il ne rend rien ;
     - <DansPanneau>  : le panneau de droite d'un cadre `plein-panneau` (Schéma) ;
                        hors coque, rendu sur place ;
     - <PiedEtape>    : le pied de l'étape (bouton d'action plein largeur). Tant
                        qu'un écran le pose, la coque retire son pied par défaut
                        (« Poser les panneaux → ») ; hors coque, rendu sur place.
   ========================================================================== */


function Portail({ cible, children, surPlaceSinon = true }) {
  const coque = useContext(ContexteCoque)
  const noeud = coque?.noeuds?.[cible] ?? null
  if (!coque) return surPlaceSinon ? children : null
  return noeud ? createPortal(children, noeud) : null
}

export function SurCarte({ children }) {
  return <Portail cible="surCarte" surPlaceSinon={false}>{children}</Portail>
}

export function DansPanneau({ children }) {
  return <Portail cible="panneau">{children}</Portail>
}

export function PiedEtape({ children }) {
  const coque = useContext(ContexteCoque)
  const prendre = coque?.prendrePied
  useEffect(() => (prendre ? prendre() : undefined), [prendre])
  return <Portail cible="pied">{children}</Portail>
}

/* Gabarit d'écran d'étape : les onglets EXISTANTS de l'étape, montés tels quels
   (mêmes props que le rail leur passe). Sert aux écrans pas encore refaits. */
export function EcranDOnglets({ cles, ...props }) {
  return (
    <div className="cal-coque-ecran">
      {cles.map((cle) => {
        const Composant = ongletParCle(cle)?.composant
        return Composant ? <Composant key={cle} {...props} /> : null
      })}
    </div>
  )
}
