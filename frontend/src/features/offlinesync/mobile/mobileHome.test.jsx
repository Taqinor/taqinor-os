import { describe, it, expect } from 'vitest'
import { defaultMobileHomeRoute } from './mobileHome'

describe('NTMOB6 — defaultMobileHomeRoute (logique pure)', () => {
  it('Technicien → /ma-journee', () => {
    expect(defaultMobileHomeRoute('Technicien')).toBe('/ma-journee')
  })

  it('Technicien responsable a son accueil d’equipe dedie (NTMOB25)', () => {
    expect(defaultMobileHomeRoute('Technicien responsable'))
      .toBe('/mobile/equipe-terrain')
  })

  it('Commercial → /mobile/commercial', () => {
    expect(defaultMobileHomeRoute('Commercial')).toBe('/mobile/commercial')
  })

  it('Commercial responsable a son accueil d’equipe dedie (NTMOB26)', () => {
    expect(defaultMobileHomeRoute('Commercial responsable'))
      .toBe('/mobile/equipe-commerciale')
  })

  it('Directeur → /mobile/cockpit', () => {
    expect(defaultMobileHomeRoute('Directeur')).toBe('/mobile/cockpit')
  })

  it('Administrateur → /mobile/cockpit', () => {
    expect(defaultMobileHomeRoute('Administrateur')).toBe('/mobile/cockpit')
  })

  it('rôle non mappé (ex. Viewer) → dashboard générique', () => {
    expect(defaultMobileHomeRoute('Viewer')).toBe('')
  })

  it('compte hérité sans rôle fin, palier admin → cockpit', () => {
    expect(defaultMobileHomeRoute(null, 'admin')).toBe('/mobile/cockpit')
  })

  it('compte hérité sans rôle fin, palier normal → dashboard générique', () => {
    expect(defaultMobileHomeRoute(null, 'normal')).toBe('')
  })

  it('aucun rôle du tout → dashboard générique', () => {
    expect(defaultMobileHomeRoute(undefined, undefined)).toBe('')
  })
})
