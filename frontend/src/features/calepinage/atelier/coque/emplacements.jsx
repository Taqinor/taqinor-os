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
                        (« Poser les panneaux → ») ; hors coque, rendu sur place ;
     - <EnTeteEtape>  : le contrôle principal, dans la rangée du titre quand le
                        panneau est le tiroir du bas (tablette), sur place sinon.
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

/* <EnTeteEtape> : le CONTRÔLE PRINCIPAL de l'étape (ex. le choix du panneau). Panneau de droite
   (bureau) : rendu sur place, dans l'écran. Tiroir du bas (tablette, téléphone — maquette Tablette) :
   posé dans la rangée du titre, entre le titre et le bouton d'action. Rendu UNE fois, jamais en double
   (au passage d'une largeur à l'autre il change de place, donc se remonte : n'y mettez pas un élément
   `rp9-*` du constructeur, seulement une re-présentation React). */
export function EnTeteEtape({ children }) {
  const coque = useContext(ContexteCoque)
  if (!coque?.tiroir) return children
  const noeud = coque.noeuds?.controle ?? null
  return noeud ? createPortal(children, noeud) : null
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
