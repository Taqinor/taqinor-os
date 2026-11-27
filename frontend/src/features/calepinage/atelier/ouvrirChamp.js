import { useEffect } from 'react'

/* ACAL397 — `?champ=<id>` : à l'arrivée sur un onglet, le panneau fait défiler
   jusqu'à l'élément d'`id` `champ` et lui donne le focus. Un `champ` sans
   élément n'ouvre que le panneau, sans erreur. Le panneau est chargé en
   différé : quelques essais brefs avant d'abandonner. */
export const PARAM_CHAMP = 'champ'

const ESSAIS = 10
const DELAI_MS = 100

/** UNE définition du défilement vers un élément (ACAL1714 : le rail s'en sert aussi pour amener son panneau en vue). */
export function amenerDansLaVue(el, block = 'center') {
  el?.scrollIntoView?.({ block })
}

export function useOuvrirChamp(champ, cleOnglet) {
  useEffect(() => {
    if (!champ) return undefined
    let essai = 0
    let minuteur = null
    const chercher = () => {
      const el = document.getElementById(champ)
      if (el) {
        amenerDansLaVue(el)
        el.focus?.()
        return
      }
      essai += 1
      if (essai < ESSAIS) minuteur = setTimeout(chercher, DELAI_MS)
    }
    chercher()
    return () => clearTimeout(minuteur)
  }, [champ, cleOnglet])
}
