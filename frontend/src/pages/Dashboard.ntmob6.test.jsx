import { describe, it, expect } from 'vitest'
import { mobileHomeAction } from './Dashboard.jsx'

/* NTMOB6 — sélecteur de démarrage par rôle. Comme Dashboard.cockpit.test.jsx,
   on teste la fonction PURE qui décide quoi faire, sans monter le composant
   ni le store (Dashboard dépend de trop de slices Redux pour un mount léger
   — cohérent avec les autres tests de ce fichier). */
describe('mobileHomeAction (NTMOB6)', () => {
  it('desktop → aucune action, quel que soit le réglage', () => {
    expect(mobileHomeAction({
      isMobile: false, hasFullProfile: true, mobileHomeRoute: null,
      roleNom: 'Commercial', roleTier: 'normal',
    })).toBeNull()
  })

  it('profil pas encore chargé (stub post-login) → aucune action', () => {
    expect(mobileHomeAction({
      isMobile: true, hasFullProfile: false, mobileHomeRoute: undefined,
      roleNom: null, roleTier: null,
    })).toBeNull()
  })

  it('route déjà mémorisée → navigue directement dessus', () => {
    expect(mobileHomeAction({
      isMobile: true, hasFullProfile: true, mobileHomeRoute: '/mobile/commercial',
      roleNom: 'Commercial', roleTier: 'normal',
    })).toEqual({ type: 'navigate', to: '/mobile/commercial' })
  })

  it('opt-out explicite (\'\') → aucune action (dashboard classique)', () => {
    expect(mobileHomeAction({
      isMobile: true, hasFullProfile: true, mobileHomeRoute: '',
      roleNom: 'Commercial', roleTier: 'normal',
    })).toBeNull()
  })

  it('pas encore décidé (null) + Technicien → décide /ma-journee', () => {
    expect(mobileHomeAction({
      isMobile: true, hasFullProfile: true, mobileHomeRoute: null,
      roleNom: 'Technicien', roleTier: 'normal',
    })).toEqual({ type: 'decide', suggested: '/ma-journee' })
  })

  it('pas encore décidé (undefined) + Directeur → décide /mobile/cockpit', () => {
    expect(mobileHomeAction({
      isMobile: true, hasFullProfile: true, mobileHomeRoute: undefined,
      roleNom: 'Directeur', roleTier: 'admin',
    })).toEqual({ type: 'decide', suggested: '/mobile/cockpit' })
  })

  it('pas encore décidé + rôle non mappé → décide une suggestion vide (dashboard)', () => {
    expect(mobileHomeAction({
      isMobile: true, hasFullProfile: true, mobileHomeRoute: null,
      roleNom: 'Viewer', roleTier: 'normal',
    })).toEqual({ type: 'decide', suggested: '' })
  })
})
