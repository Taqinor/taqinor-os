import { describe, it, expect, beforeEach } from 'vitest'
import {
  buildOnboardingSteps,
  isCompanyProfileComplete,
  countFromListResponse,
  isOnboardingDismissed,
  dismissOnboarding,
} from './onboardingHelpers'

/* VX36 — L'onboarding sort de sa cachette. Tests des fonctions PURES qui
   pilotent la bannière : dérivation des 3 étapes + rejet PAR SOCIÉTÉ. */

describe('buildOnboardingSteps (VX36)', () => {
  const fullProfile = { nom: 'ACME', adresse: '1 rue', email: 'a@b.co' }
  it('les 3 étapes à faire quand rien n’est configuré', () => {
    const steps = buildOnboardingSteps({ profile: null, produitCount: 0, userCount: 1 })
    expect(steps).toHaveLength(3)
    expect(steps.map((s) => s.done)).toEqual([false, false, false])
    expect(steps.map((s) => s.key)).toEqual(['profil', 'produit', 'equipe'])
  })
  it('marque les étapes faites selon le profil / les comptes', () => {
    const steps = buildOnboardingSteps({ profile: fullProfile, produitCount: 3, userCount: 2 })
    expect(steps.map((s) => s.done)).toEqual([true, true, true])
  })
  it('« équipe » n’est faite qu’avec un compte AU-DELÀ du sien (> 1)', () => {
    const one = buildOnboardingSteps({ profile: fullProfile, produitCount: 1, userCount: 1 })
    expect(one.find((s) => s.key === 'equipe').done).toBe(false)
    const two = buildOnboardingSteps({ profile: fullProfile, produitCount: 1, userCount: 2 })
    expect(two.find((s) => s.key === 'equipe').done).toBe(true)
  })
  it('des comptes null (lecture API échouée) → étapes « à faire », jamais d’erreur', () => {
    const steps = buildOnboardingSteps({ profile: fullProfile, produitCount: null, userCount: null })
    expect(steps.find((s) => s.key === 'produit').done).toBe(false)
    expect(steps.find((s) => s.key === 'equipe').done).toBe(false)
  })
})

describe('isCompanyProfileComplete (rappel FG16)', () => {
  it('exige nom + adresse + un contact', () => {
    expect(isCompanyProfileComplete({ nom: 'A', adresse: 'B', telephone: '06' })).toBe(true)
    expect(isCompanyProfileComplete({ nom: 'A', adresse: 'B' })).toBe(false)
    expect(isCompanyProfileComplete(null)).toBe(false)
  })
})

describe('countFromListResponse', () => {
  it('gère paginé { count } et tableau brut', () => {
    expect(countFromListResponse({ count: 42, results: [] })).toBe(42)
    expect(countFromListResponse([1, 2, 3])).toBe(3)
    expect(countFromListResponse(null)).toBe(0)
  })
})

describe('rejet de la bannière PAR SOCIÉTÉ (VX36)', () => {
  beforeEach(() => {
    try { window.localStorage.clear() } catch { /* jsdom */ }
  })
  it('le rejet est scopé à la société (pas de fuite multi-tenant)', () => {
    expect(isOnboardingDismissed(7)).toBe(false)
    dismissOnboarding(7)
    expect(isOnboardingDismissed(7)).toBe(true)
    // Une AUTRE société n'est pas affectée.
    expect(isOnboardingDismissed(9)).toBe(false)
  })
  it('id absent → clé générique cohérente', () => {
    expect(isOnboardingDismissed(undefined)).toBe(false)
    dismissOnboarding(undefined)
    expect(isOnboardingDismissed(undefined)).toBe(true)
  })
})
