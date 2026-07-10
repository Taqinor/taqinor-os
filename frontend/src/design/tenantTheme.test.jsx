import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import {
  normalizeTenantTheme, applyTenantTheme, clearTenantTheme,
  getCurrentTenantTheme, subscribeTenantTheme, setTenantTheme, resetTenantTheme,
  TENANT_THEME_VARS,
} from './tenantTheme'

/* SCA24 — thème white-label (TenantTheme) : application + repli neutre. */
describe('tenantTheme — normalisation', () => {
  it('normalise une réponse API complète', () => {
    const t = normalizeTenantTheme({
      logo_url: 'https://cdn.example.com/logo.png',
      couleur_primaire: '#112233',
      couleur_secondaire: '#445566',
      nom_affichage: 'ACME',
    })
    expect(t).toEqual({
      logoUrl: 'https://cdn.example.com/logo.png',
      couleurPrimaire: '#112233',
      couleurSecondaire: '#445566',
      nomAffichage: 'ACME',
    })
  })

  it('normalise null/undefined/objet vide en chaînes vides (jamais d’exception)', () => {
    const empty = { logoUrl: '', couleurPrimaire: '', couleurSecondaire: '', nomAffichage: '' }
    expect(normalizeTenantTheme(null)).toEqual(empty)
    expect(normalizeTenantTheme(undefined)).toEqual(empty)
    expect(normalizeTenantTheme({})).toEqual(empty)
    // Réponse API malformée (types inattendus) : jamais de crash, repli vide.
    expect(normalizeTenantTheme({ couleur_primaire: 42, logo_url: null })).toEqual(empty)
  })
})

describe('tenantTheme — applyTenantTheme (DOM)', () => {
  afterEach(() => {
    clearTenantTheme()
  })

  it('pose les variables CSS quand le thème est renseigné', () => {
    applyTenantTheme({
      logo_url: '/media/theme/logo.png',
      couleur_primaire: '#1a3b8c',
      couleur_secondaire: '#f5c100',
    })
    const root = document.documentElement
    expect(root.style.getPropertyValue(TENANT_THEME_VARS.primary)).toBe('#1a3b8c')
    expect(root.style.getPropertyValue(TENANT_THEME_VARS.secondary)).toBe('#f5c100')
    expect(root.style.getPropertyValue(TENANT_THEME_VARS.logo)).toContain('/media/theme/logo.png')
  })

  it('repli neutre : thème vide efface les variables (aucune couleur orpheline)', () => {
    applyTenantTheme({ couleur_primaire: '#1a3b8c' })
    expect(document.documentElement.style.getPropertyValue(TENANT_THEME_VARS.primary)).toBe('#1a3b8c')

    applyTenantTheme(null)
    expect(document.documentElement.style.getPropertyValue(TENANT_THEME_VARS.primary)).toBe('')
    expect(document.documentElement.style.getPropertyValue(TENANT_THEME_VARS.secondary)).toBe('')
    expect(document.documentElement.style.getPropertyValue(TENANT_THEME_VARS.logo)).toBe('')
  })

  it('clearTenantTheme() efface explicitement toute variable posée', () => {
    applyTenantTheme({ couleur_primaire: '#000000', logo_url: '/x.png' })
    clearTenantTheme()
    const root = document.documentElement
    expect(root.style.getPropertyValue(TENANT_THEME_VARS.primary)).toBe('')
    expect(root.style.getPropertyValue(TENANT_THEME_VARS.logo)).toBe('')
  })
})

describe('tenantTheme — pub/sub (consommé par Header sans refetch)', () => {
  beforeEach(() => {
    resetTenantTheme()
  })
  afterEach(() => {
    resetTenantTheme()
  })

  it('getCurrentTenantTheme() reflète le dernier thème appliqué via setTenantTheme', () => {
    setTenantTheme({ nom_affichage: 'ACME', couleur_primaire: '#123456' })
    expect(getCurrentTenantTheme().nomAffichage).toBe('ACME')
    expect(getCurrentTenantTheme().couleurPrimaire).toBe('#123456')
  })

  it('resetTenantTheme() republie un thème neutre (nomAffichage vide)', () => {
    setTenantTheme({ nom_affichage: 'ACME' })
    resetTenantTheme()
    expect(getCurrentTenantTheme().nomAffichage).toBe('')
  })

  it('subscribeTenantTheme notifie les abonnés à chaque changement', () => {
    const seen = []
    const unsubscribe = subscribeTenantTheme((t) => seen.push(t.nomAffichage))
    setTenantTheme({ nom_affichage: 'Client A' })
    setTenantTheme({ nom_affichage: 'Client B' })
    unsubscribe()
    setTenantTheme({ nom_affichage: 'Client C — pas reçu' })
    expect(seen).toEqual(['Client A', 'Client B'])
  })
})
