import { describe, it, expect } from 'vitest'
import {
  LOGOUT_EVENT, getPrefetched, setPrefetched, resetPrefetchCache,
} from './leadPrefetch'

// LW45 — hygiène résiduelle : sur un poste PARTAGÉ, le cache de préchargement
// (TTL 60s) survivait à une déconnexion — un utilisateur B se connectant dans
// cette fenêtre pouvait hériter des données pré-chargées de l'utilisateur A
// précédent au premier rendu J/K (LOAD_LEAD → withPrefetched). Ce test vit en
// `.test.jsx` (vitest/jsdom, PAS le `.test.mjs` node:test de ce même module —
// `window` n'y existe pas) puisqu'il exerce précisément l'écouteur `window`.
// `leadPrefetch.test.mjs` (node:test, logique pure) reste inchangé.

describe('LW45 — leadPrefetch : cache vidé sur déconnexion', () => {
  it('LOGOUT_EVENT dispatché sur window → le cache est vidé', () => {
    resetPrefetchCache()
    setPrefetched(1, { id: 1, nom: 'Ali' })
    expect(getPrefetched(1)).toEqual({ id: 1, nom: 'Ali' })
    window.dispatchEvent(new Event(LOGOUT_EVENT))
    expect(getPrefetched(1)).toBeNull()
  })
})
