// NTMOB24 — combien de modifications attendent la synchro, PAR ENREGISTREMENT.
//
// Le bandeau global (NTMOB3) dit « 3 opérations en attente » ; il ne dit pas
// LESQUELLES. Ce hook rend ce détail exploitable dans une liste : il renvoie
// une `Map<String(id), n>` que l'écran consulte pour chaque ligne.
//
// Il ne crée AUCUNE file et AUCUN compteur : il LIT l'outbox unique (décision
// VX105) — files par module (NTMOB1) et, si l'écran le demande, la file terrain
// historique dont la cible vit dans le corps de l'op (`payload.chantier`,
// `payload.intervention`). Un seul abonnement pour toute la liste : jamais un
// hook par ligne (N lectures IndexedDB pour un tableau de 200 lignes).
import { useCallback, useEffect, useState } from 'react'
import {
  countByPayloadKey, onOfflineOutboxChange, pendingCountByTarget,
} from '../../lib/offlineOutbox'
import { fieldOutbox } from '../../features/installations/offline/fieldOutbox'

const VIDE = new Map()

/**
 * @param {string} module  module hors-ligne (`crm`, `ventes`, `stock`,
 *                         `installations`, `sav`).
 * @param {{champ?: string}} options  `champ` = clé du corps des ops de la file
 *                         TERRAIN à agréger en plus (ex. 'chantier').
 * @returns {Map<string, number>} id de l'enregistrement → nb d'ops en attente.
 */
export function useOfflinePending(module, { champ } = {}) {
  const [compte, setCompte] = useState(VIDE)

  const rafraichir = useCallback(async () => {
    try {
      const total = await pendingCountByTarget(module)
      if (champ) {
        const terrain = countByPayloadKey(await fieldOutbox.pending(), champ)
        for (const [cle, n] of terrain) total.set(cle, (total.get(cle) || 0) + n)
      }
      setCompte(total)
    } catch { /* défensif : un badge ne casse jamais une liste */ }
  }, [module, champ])

  useEffect(() => {
    // Lecture initiale d'un état EXTERNE (IndexedDB) → c'est exactement le rôle
    // d'un effet de synchronisation.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    rafraichir()
    const desabonner = onOfflineOutboxChange(rafraichir)
    if (typeof window === 'undefined') return desabonner
    window.addEventListener('online', rafraichir)
    window.addEventListener('offline', rafraichir)
    return () => {
      desabonner()
      window.removeEventListener('online', rafraichir)
      window.removeEventListener('offline', rafraichir)
    }
  }, [rafraichir])

  return compte
}
