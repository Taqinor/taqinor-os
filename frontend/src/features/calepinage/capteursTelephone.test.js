import { afterEach, describe, expect, it } from 'vitest'
import { arreter, demarrerCapteurs, lireInclinaison, lireVisee } from './capteursTelephone'

function fauxWindow(permission) {
  const w = new EventTarget()
  w.DeviceOrientationEvent = permission === undefined ? function Evt() {} : { requestPermission: async () => permission }
  w.emettre = (nom, champs) => w.dispatchEvent(Object.assign(new Event(nom), champs))
  return w
}

afterEach(() => arreter())

describe('ACAL516 — capteurs du téléphone', () => {
  it('cap iOS 90 et beta 90 : azimut 90, hauteur 0', async () => {
    const w = fauxWindow('granted')
    expect((await demarrerCapteurs(w)).ok).toBe(true)
    w.emettre('deviceorientation', { webkitCompassHeading: 90, beta: 90, gamma: 0, alpha: 0 })
    const v = lireVisee()
    expect(v.azimutDeg).toBeCloseTo(90, 5)
    expect(v.hauteurDeg).toBeCloseTo(0, 5)
  })

  it('beta 120 : hauteur positive (arrière du téléphone au-dessus de l’horizon)', async () => {
    const w = fauxWindow()
    await demarrerCapteurs(w)
    w.emettre('deviceorientationabsolute', { alpha: 0, beta: 120, gamma: 0, absolute: true })
    expect(lireVisee().hauteurDeg).toBeCloseTo(30, 5)
    expect(lireInclinaison()).toEqual({ betaDeg: 120, gammaDeg: 0 })
  })

  it('permission refusée : indisponible, motif français, aucune lecture', async () => {
    const w = fauxWindow('denied')
    const r = await demarrerCapteurs(w)
    expect(r.indisponible).toBe(true)
    expect(r.motif).toContain('saisissez l’azimut et la hauteur à la main')
    w.emettre('deviceorientation', { webkitCompassHeading: 90, beta: 90, gamma: 0 })
    expect(lireVisee().indisponible).toBe(true)
  })

  it('aucun événement reçu ou événement sans angles : indisponible', async () => {
    const w = fauxWindow()
    await demarrerCapteurs(w)
    expect(lireVisee().indisponible).toBe(true)
    w.emettre('deviceorientation', { alpha: null, beta: null, gamma: null })
    expect(lireVisee().indisponible).toBe(true)
  })

  it('capteur absent : indisponible', async () => {
    expect((await demarrerCapteurs({})).indisponible).toBe(true)
  })
})
