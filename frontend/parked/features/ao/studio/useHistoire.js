import { useCallback, useMemo, useRef, useState } from 'react'

/* ============================================================================
   AOF76 — Historique undo/redo PARTAGÉ de l'atelier.
   ----------------------------------------------------------------------------
   Un SEUL historique par atelier, volontairement : le canvas (AOF76) et le
   tableau de géométrie éditable au clavier (AOF77) sont deux VOIES vers la même
   géométrie ; deux piles séparées produiraient un « annuler » qui ne défait pas
   ce que l'utilisateur vient de faire. Le propriétaire de l'atelier crée
   l'historique et passe `appliquer` aux deux voies.

   Chaque opération porte un LIBELLÉ (« Déplacer le sommet B », « Accrocher au
   sommet A », « Pivoter de 15° ») : l'accrochage n'est pas un effet de bord
   invisible, c'est une opération annulable comme une autre — exigence
   explicite du contrat.

   `fusion` sert au geste CONTINU : un glissement de souris produit des dizaines
   d'états intermédiaires ; on les fusionne sous une même clé pour que « annuler »
   défasse LE GESTE, pas la dernière micro-position. La fusion se ferme
   explicitement (`terminer()`) au relâchement du pointeur.
   ========================================================================== */

export const LIMITE_HISTORIQUE = 200

export function useHistoire(etatInitial, options = {}) {
  const { limite = LIMITE_HISTORIQUE } = options
  const [pile, setPile] = useState(() => ({
    passe: [],
    present: { etat: etatInitial, libelle: 'État initial' },
    futur: [],
  }))
  // Clé du geste en cours (fusion) — une ref : elle doit être lue/écrite
  // pendant un glissement sans provoquer de rendu.
  const fusionRef = useRef(null)

  const appliquer = useCallback((suivant, libelle = 'Modification', opts = {}) => {
    const { fusion = null } = opts
    setPile((p) => {
      const etat = typeof suivant === 'function' ? suivant(p.present.etat) : suivant
      if (etat === p.present.etat) return p
      const entree = { etat, libelle }
      // Geste continu déjà ouvert sous la même clé → on remplace le présent
      // au lieu d'empiler un cran d'annulation par pixel parcouru.
      if (fusion && fusionRef.current === fusion) {
        return { ...p, present: entree, futur: [] }
      }
      if (fusion) fusionRef.current = fusion
      const passe = [...p.passe, p.present].slice(-limite)
      return { passe, present: entree, futur: [] }
    })
  }, [limite])

  /** Ferme le geste en cours : le prochain `appliquer` empilera un vrai cran. */
  const terminer = useCallback(() => { fusionRef.current = null }, [])

  const annuler = useCallback(() => {
    fusionRef.current = null
    setPile((p) => {
      if (p.passe.length === 0) return p
      const precedent = p.passe[p.passe.length - 1]
      return {
        passe: p.passe.slice(0, -1),
        present: precedent,
        futur: [p.present, ...p.futur],
      }
    })
  }, [])

  const retablir = useCallback(() => {
    fusionRef.current = null
    setPile((p) => {
      if (p.futur.length === 0) return p
      const [suivant, ...reste] = p.futur
      return { passe: [...p.passe, p.present], present: suivant, futur: reste }
    })
  }, [])

  const reinitialiser = useCallback((etat, libelle = 'État initial') => {
    fusionRef.current = null
    setPile({ passe: [], present: { etat, libelle }, futur: [] })
  }, [])

  return useMemo(() => ({
    etat: pile.present.etat,
    libelle: pile.present.libelle,
    appliquer,
    terminer,
    annuler,
    retablir,
    reinitialiser,
    peutAnnuler: pile.passe.length > 0,
    peutRetablir: pile.futur.length > 0,
    libelleAnnuler: pile.present.libelle,
    libelleRetablir: pile.futur[0]?.libelle ?? null,
  }), [pile, appliquer, terminer, annuler, retablir, reinitialiser])
}

export default useHistoire
