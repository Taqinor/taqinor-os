import { describe, it, expect, vi, beforeEach } from 'vitest'
// NTMOB12 — compressImage() dépend du décodage d'image (Image/canvas), non
// fiable en jsdom : mocké pour vérifier que compressPhotoForUpload DÉLÈGUE
// correctement, sans tester compressImage lui-même (hors périmètre ici).
vi.mock('../../ui/file-utils', () => ({
  compressImage: vi.fn((f) => Promise.resolve(
    new File([f], 'compressed.jpg', { type: 'image/jpeg' }))),
}))
import {
  getLandingModule, setLandingModule, resolveLandingPath, getLastModuleSegment,
  getReducedMotionPref, setReducedMotionPref, applyReducedMotion,
  getPhotoQualityPref, setPhotoQualityPref, compressPhotoForUpload,
} from './prefs'
import { compressImage } from '../../ui/file-utils'

const LANDING_KEY = 'taqinor.landingModule'
const REDUCED_MOTION_KEY = 'taqinor.reducedMotion'
const LAST_MODULE_KEY = 'taqinor.lastModule'
const PHOTO_QUALITY_KEY = 'taqinor.photoQuality'

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
    window.localStorage.removeItem(PHOTO_QUALITY_KEY)
    document.documentElement.removeAttribute('data-reduced-motion')
    document.getElementById('taqinor-reduced-motion-override')?.remove()
    compressImage.mockClear()
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

  describe('NTMOB12 — qualité photo (Standard compressé / Original)', () => {
    it('défaut = compressed (comportement historique inchangé)', () => {
      expect(getPhotoQualityPref()).toBe('compressed')
    })

    it('persiste "original" puis se relit', () => {
      setPhotoQualityPref('original')
      expect(getPhotoQualityPref()).toBe('original')
    })

    it('repasser à "compressed" efface la clé (repli défaut)', () => {
      setPhotoQualityPref('original')
      setPhotoQualityPref('compressed')
      expect(getPhotoQualityPref()).toBe('compressed')
      expect(window.localStorage.getItem(PHOTO_QUALITY_KEY)).toBeNull()
    })

    it('compressPhotoForUpload délègue à compressImage() par défaut', async () => {
      const file = new File(['x'], 'a.jpg', { type: 'image/jpeg' })
      const out = await compressPhotoForUpload(file)
      expect(compressImage).toHaveBeenCalledWith(file)
      expect(out.name).toBe('compressed.jpg')
    })

    it('compressPhotoForUpload est un passthrough total quand "original"', async () => {
      setPhotoQualityPref('original')
      const file = new File(['x'], 'a.jpg', { type: 'image/jpeg' })
      const out = await compressPhotoForUpload(file)
      expect(compressImage).not.toHaveBeenCalled()
      expect(out).toBe(file)
    })
  })
})
