import { useEffect, useRef, useState } from 'react'
import { cn } from '../lib/cn'

/* ============================================================================
   EDC3 — BARRE DE DÉFILEMENT HORIZONTALE COLLANTE (fondateur 09/10/2026).
   « Dans la table il faut descendre, glisser à gauche, remonter, redescendre,
   glisser à droite — un bazar. S'il faut un défilement horizontal, il doit
   être possible à CHAQUE hauteur de la table, jamais à aller chercher en bas. »

   Rend le conteneur de la table (`.bdc-wrap`, défilable) puis, en FRÈRE, une
   barre « proxy » `position: sticky; bottom` (`.bdc-proxy`) : elle reste collée
   au bas du défileur réel (`.ldp-edit` dans le panneau, `.layout-content` en
   page) tant que la table est à l'écran, et les deux `scrollLeft` se
   recopient dans les deux sens.

   Deux états, exposés par `data-deborde` sur le conteneur :
     · « tient » (scrollWidth ≤ clientWidth + 1) — pas de barre ; la feuille de
       style peut alors laisser le conteneur en `overflow: visible` (l'en-tête
       de la table des lignes colle au défileur, EDC3) ;
     · « déborde » — barre proxy rendue, barre NATIVE du conteneur masquée
       (une seule barre à l'écran, jamais deux).

   Mesures testées sous Chromium 149 (09/10) :
     · ResizeObserver sur le conteneur ET sur la table (premier enfant) :
       observer le conteneur seul ne voit pas une colonne ajoutée ;
     · recopie à 0,5 px de tolérance — une seule écriture par défilement réel,
       jamais de boucle conteneur → barre → conteneur ;
     · jamais `setInterval`, jamais `position: fixed` (le panneau Sheet garde un
       `transform` après son animation : un `fixed` y serait piégé).

   La piste est VISIBLE même sous les barres « overlay » de macOS : le style
   `::-webkit-scrollbar` d'`index.css` (bloc EDC3) force une barre classique,
   ignoré si `scrollbar-width` ≠ `auto` — d'où `scrollbar-width: auto` sur la
   barre. Aucune règle métier, aucune dépendance.
   ========================================================================== */
// `bottom` : optionnel — sans lui, la feuille de style décide (`.bdc-proxy
// { bottom: 0 }`, bloc EDC3 d'index.css) ; un appelant dont le défileur porte
// un bandeau collant au bas peut le passer.
export function BarreDefilementCollante({ bottom, className, children, ...props }) {
  const wrapRef = useRef(null)
  const barreRef = useRef(null)
  const [dims, setDims] = useState({ scroll: 0, client: 0, barre: 0 })

  useEffect(() => {
    const wrap = wrapRef.current
    const barre = barreRef.current
    if (!wrap || !barre) return undefined
    const mesurer = () => {
      const scroll = wrap.scrollWidth
      const client = wrap.clientWidth
      const largeurBarre = barre.clientWidth
      setDims((d) => (d.scroll === scroll && d.client === client && d.barre === largeurBarre
        ? d : { scroll, client, barre: largeurBarre }))
    }
    // Synchronisation de `scrollLeft` : n'écrit que sur un écart réel (> 0,5 px) — le
    // `scroll` que cette écriture déclenche en retour trouve un écart nul.
    const miroir = (source, cible) => () => {
      if (Math.abs(cible.scrollLeft - source.scrollLeft) > 0.5) cible.scrollLeft = source.scrollLeft
    }
    const surWrap = miroir(wrap, barre)
    const surBarre = miroir(barre, wrap)
    wrap.addEventListener('scroll', surWrap, { passive: true })
    barre.addEventListener('scroll', surBarre, { passive: true })
    let observateur = null
    if (typeof ResizeObserver !== 'undefined') {
      observateur = new ResizeObserver(mesurer)
      observateur.observe(wrap)
      // La TABLE (et tout enfant direct) : une colonne ajoutée l'élargit sans
      // changer la taille du conteneur.
      for (const enfant of wrap.children) observateur.observe(enfant)
      // La barre elle-même : sa largeur réelle n'est connue qu'une fois rendue.
      observateur.observe(barre)
    }
    mesurer()
    return () => {
      observateur?.disconnect()
      wrap.removeEventListener('scroll', surWrap)
      barre.removeEventListener('scroll', surBarre)
    }
  }, [])

  const deborde = dims.scroll > dims.client + 1

  // Au passage en « déborde » (ou quand la table s'élargit), la barre reprend
  // la position courante du conteneur.
  useEffect(() => {
    const wrap = wrapRef.current
    const barre = barreRef.current
    if (deborde && wrap && barre) barre.scrollLeft = wrap.scrollLeft
  }, [deborde, dims.scroll])

  // Même course de défilement des deux côtés : la piste vaut la largeur
  // défilable du conteneur + la largeur visible de la barre (le conteneur peut
  // porter une bordure que la barre n'a pas).
  const largeurPiste = Math.max(0, dims.scroll - dims.client + (dims.barre || dims.client))

  return (
    <>
      <div
        ref={wrapRef}
        className={cn('bdc-wrap', className)}
        data-deborde={deborde ? 'true' : 'false'}
        {...props}
      >
        {children}
      </div>
      {/* Doublon visuel de la barre native (masquée) : caché aux lecteurs
          d'écran et hors de l'ordre de tabulation — le contenu reste
          atteignable au clavier dans le conteneur lui-même. */}
      <div
        ref={barreRef}
        className="bdc-proxy"
        aria-hidden="true"
        tabIndex={-1}
        hidden={!deborde}
        style={bottom == null ? { position: 'sticky' } : { position: 'sticky', bottom }}
      >
        <div className="bdc-proxy-piste" style={{ width: largeurPiste, height: 1 }} />
      </div>
    </>
  )
}

export default BarreDefilementCollante
