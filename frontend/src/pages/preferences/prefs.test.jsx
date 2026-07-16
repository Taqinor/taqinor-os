import { describe, it, expect, beforeEach } from 'vitest'
import {
  getLandingModule, setLandingModule, resolveLandingPath, getLastModuleSegment,
  getReducedMotionPref, setReducedMotionPref, applyReducedMotion,
} from './prefs'

const LANDING_KEY = 'taqinor.landingModule'
const REDUCED_MOTION_KEY = 'taqinor.reducedMotion'
const LAST_MODULE_KEY = 'taqinor.lastModule'

const CONFIGS = [
  { key: 'compta', nav: { label: 'COMPTABILITÉ', items: [{ to: '/comptabilite' }] } },
  { key: 'rh', nav: { label: 'RH', items: [{ to: '/rh' }] } },
  { key: 'routes_only' }, // pas de section nav (comme admin/crm/ventes/...) — ignoré.
]

describe('VX46 — prefs.js (logique pure, persistance localStorage)', () => {
  beforeEach(() => {
    window.localStorage.removeItem(LANDING_KEY)
    window.localStorage.removeItem(REDUCED_MOTION_KEY)
    window.localStorage.removeItem(LAST_MODULE_KEY)
    document.documentElement.removeAttribute('data-reduced-motion')
    document.getElementById('taqinor-reduced-motion-override')?.remove()
  })

  it('module d’atterrissage : persiste et se relit', () => {
    expect(getLandingModule()).toBe('')
    setLandingModule('rh')
    expect(getLandingModule()).toBe('rh')
    setLandingModule('')
    expect(getLandingModule()).toBe('')
  })

  it('resolveLandingPath : préférence explicite → cockpit du module choisi', () => {
    setLandingModule('rh')
    expect(resolveLandingPath(CONFIGS, '')).toBe('/rh')
  })

  it('resolveLandingPath : préférence vide → dernier module visité (VX11)', () => {
    expect(resolveLandingPath(CONFIGS, 'compta')).toBe('/comptabilite')
  })

  it('resolveLandingPath : repli /dashboard quand rien n’est connu', () => {
    expect(resolveLandingPath(CONFIGS, '')).toBe('/dashboard')
  })

  it('resolveLandingPath : repli /dashboard si le module choisi a disparu de moduleConfigs', () => {
    setLandingModule('module-supprime')
    expect(resolveLandingPath(CONFIGS, '')).toBe('/dashboard')
  })

  it('getLastModuleSegment lit taqinor.lastModule (VX11)', () => {
    window.localStorage.setItem(LAST_MODULE_KEY, 'rh')
    expect(getLastModuleSegment()).toBe('rh')
  })

  it('réduction de mouvement : persiste et applique l’attribut sur <html>', () => {
    expect(getReducedMotionPref()).toBe(false)
    setReducedMotionPref(true)
    expect(getReducedMotionPref()).toBe(true)
    expect(document.documentElement.getAttribute('data-reduced-motion')).toBe('true')
    setReducedMotionPref(false)
    expect(document.documentElement.getAttribute('data-reduced-motion')).toBe('false')
  })

  it('applyReducedMotion pose UNE SEULE feuille de style singleton dans <head>', () => {
    applyReducedMotion(true)
    applyReducedMotion(true)
    const tags = document.querySelectorAll('#taqinor-reduced-motion-override')
    expect(tags.length).toBe(1)
  })
})
