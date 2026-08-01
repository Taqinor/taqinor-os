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
  LANDING_LAST_MODULE,
  getReducedMotionPref, setReducedMotionPref, applyReducedMotion,
  getPhotoQualityPref, setPhotoQualityPref, compressPhotoForUpload,
  getAppResumePref, setAppResumePref,
  APP_RESUME_KEY, APP_RESUME_ASK, APP_RESUME_ALWAYS, APP_RESUME_NEVER,
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
    window.localStorage.removeItem(APP_RESUME_KEY)
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

  it('resolveLandingPath : préférence explicite « dernier module » → ce module (VX11)', () => {
    setLandingModule(LANDING_LAST_MODULE)
    expect(resolveLandingPath(CONFIGS, 'compta')).toBe('/comptabilite')
  })

  // ODY3 — le repli n'est plus `/dashboard` mais le Menu d'accueil `/apps` :
  // ouvrir l'ERP, c'est voir SES apps. `/dashboard` reste une route valide.
  it('resolveLandingPath : repli /apps quand rien n’est connu (ODY3)', () => {
    expect(resolveLandingPath(CONFIGS, '')).toBe('/apps')
  })

  it('resolveLandingPath : repli /apps si le module choisi a disparu de moduleConfigs', () => {
    setLandingModule('module-supprime')
    expect(resolveLandingPath(CONFIGS, '')).toBe('/apps')
  })

  it('resolveLandingPath : mono-app → on entre directement dans l’unique app (ODY3)', () => {
    const apps = [{ key: 'rh', to: '/rh' }]
    expect(resolveLandingPath(CONFIGS, '', { apps })).toBe('/rh')
  })

  it('resolveLandingPath : deux apps ou plus → Menu d’accueil (jamais un choix arbitraire)', () => {
    const apps = [{ key: 'rh', to: '/rh' }, { key: 'compta', to: '/comptabilite' }]
    expect(resolveLandingPath(CONFIGS, '', { apps })).toBe('/apps')
  })

  it('resolveLandingPath : la préférence VX46 reste PRIORITAIRE sur le mono-app', () => {
    setLandingModule('compta')
    const apps = [{ key: 'rh', to: '/rh' }]
    expect(resolveLandingPath(CONFIGS, '', { apps })).toBe('/comptabilite')
  })

  // ODY3 — « dernier module visité » n'est PLUS le défaut implicite : sans
  // préférence explicite, on atterrit sur le Menu d'accueil (ou dans l'unique
  // app en mono-app). Sinon le paradigme « j'ouvre → MES apps » n'aurait jamais
  // été vu par un utilisateur de retour.
  it('resolveLandingPath : sans préférence, le dernier module visité est IGNORÉ (ODY3)', () => {
    expect(resolveLandingPath(CONFIGS, 'compta')).toBe('/apps')
  })

  it('resolveLandingPath : sans préférence, le mono-app prime sur le dernier module visité', () => {
    const apps = [{ key: 'rh', to: '/rh' }]
    expect(resolveLandingPath(CONFIGS, 'compta', { apps })).toBe('/rh')
  })

  it('resolveLandingPath : « dernier module visité » CHOISI explicitement est honoré (VX11)', () => {
    setLandingModule(LANDING_LAST_MODULE)
    const apps = [{ key: 'rh', to: '/rh' }]
    expect(resolveLandingPath(CONFIGS, 'compta', { apps })).toBe('/comptabilite')
  })

  it('resolveLandingPath : « dernier module visité » choisi mais aucun module connu → Menu d’accueil', () => {
    setLandingModule(LANDING_LAST_MODULE)
    expect(resolveLandingPath(CONFIGS, '')).toBe('/apps')
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

  describe('ODY29 — à l’ouverture d’une app (proposer / toujours / jamais)', () => {
    it('défaut = proposer (aucune clé écrite)', () => {
      expect(getAppResumePref()).toBe(APP_RESUME_ASK)
      expect(window.localStorage.getItem(APP_RESUME_KEY)).toBeNull()
    })

    it('persiste « toujours reprendre » puis « toujours le cockpit »', () => {
      setAppResumePref(APP_RESUME_ALWAYS)
      expect(getAppResumePref()).toBe(APP_RESUME_ALWAYS)
      setAppResumePref(APP_RESUME_NEVER)
      expect(getAppResumePref()).toBe(APP_RESUME_NEVER)
    })

    it('revenir au défaut efface la clé', () => {
      setAppResumePref(APP_RESUME_ALWAYS)
      setAppResumePref(APP_RESUME_ASK)
      expect(getAppResumePref()).toBe(APP_RESUME_ASK)
      expect(window.localStorage.getItem(APP_RESUME_KEY)).toBeNull()
    })

    it('une valeur inconnue en stockage retombe sur le défaut', () => {
      window.localStorage.setItem(APP_RESUME_KEY, 'n’importe quoi')
      expect(getAppResumePref()).toBe(APP_RESUME_ASK)
    })
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
