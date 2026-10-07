import { describe, it, expect } from 'vitest'
import { mobileHomeAction } from '../features/offlinesync/mobile/mobileHome.js'

/* NTMOB6 — sélecteur de démarrage par rôle. Comme Dashboard.cockpit.test.jsx,
   on teste la fonction PURE qui décide quoi faire, sans monter le composant
   ni le store (Dashboard dépend de trop de slices Redux pour un mount léger
   — cohérent avec les autres tests de ce fichier).

   ALEA31 — la décision vit dans `mobileHome.js` et la route suggérée vient du
   SERVEUR (`/auth/me/` → `mobile_home_route_suggeree`) : les valeurs
   ci-dessous sont celles que `default_mobile_home_route` sert. */
const SERVEUR = {
  Commercial: '/mobile/commercial',
  Technicien: '/ma-journee',
  Directeur: '/mobile/cockpit',
  Viewer: '',
}

describe('mobileHomeAction (NTMOB6)', () => {
  it('desktop → aucune action, quel que soit le réglage', () => {
    expect(mobileHomeAction({
      isMobile: false, hasFullProfile: true, mobileHomeRoute: null,
      suggestedRoute: SERVEUR.Commercial,
    })).toBeNull()
  })

  it('profil pas encore chargé (stub post-login) → aucune action', () => {
    expect(mobileHomeAction({
      isMobile: true, hasFullProfile: false, mobileHomeRoute: undefined,
      suggestedRoute: undefined,
    })).toBeNull()
  })

  it('route déjà mémorisée → navigue directement dessus', () => {
    expect(mobileHomeAction({
      isMobile: true, hasFullProfile: true, mobileHomeRoute: '/mobile/commercial',
      suggestedRoute: SERVEUR.Commercial,
    })).toEqual({ type: 'navigate', to: '/mobile/commercial' })
  })

  it('opt-out explicite (\'\') → aucune action (dashboard classique)', () => {
    expect(mobileHomeAction({
      isMobile: true, hasFullProfile: true, mobileHomeRoute: '',
      suggestedRoute: SERVEUR.Commercial,
    })).toBeNull()
  })

  it('pas encore décidé (null) + Technicien → décide /ma-journee', () => {
    expect(mobileHomeAction({
      isMobile: true, hasFullProfile: true, mobileHomeRoute: null,
      suggestedRoute: SERVEUR.Technicien,
    })).toEqual({ type: 'decide', suggested: '/ma-journee' })
  })

  it('pas encore décidé (undefined) + Directeur → décide /mobile/cockpit', () => {
    expect(mobileHomeAction({
      isMobile: true, hasFullProfile: true, mobileHomeRoute: undefined,
      suggestedRoute: SERVEUR.Directeur,
    })).toEqual({ type: 'decide', suggested: '/mobile/cockpit' })
  })

  it('pas encore décidé + rôle non mappé → décide une suggestion vide (dashboard)', () => {
    expect(mobileHomeAction({
      isMobile: true, hasFullProfile: true, mobileHomeRoute: null,
      suggestedRoute: SERVEUR.Viewer,
    })).toEqual({ type: 'decide', suggested: '' })
  })
})
