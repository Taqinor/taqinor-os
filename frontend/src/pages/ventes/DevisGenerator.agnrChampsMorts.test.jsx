// AGNR26 — le champ mort « Heures de pompage effectives / jour » n'est plus
// rendu (plus rien ne le lisait depuis AGR114/AGR130) ; un brouillon ancien
// qui le porte se restaure sans erreur.
//
// Run : npx vitest run src/pages/ventes/DevisGenerator.agnrChampsMorts.test.jsx
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { act, cleanup, fireEvent, screen } from '@testing-library/react'

import { DATE_FIGEE, monter, attendreStable } from './DevisGeneratorGoldenHarnais'

const { apiAuto } = vi.hoisted(() => ({
  apiAuto: () => {
    const fns = {}
    return {
      default: new Proxy(fns, {
        get(cible, cle) {
          if (typeof cle !== 'string' || cle === 'then' || cle === '__esModule') return undefined
          if (!cible[cle]) cible[cle] = vi.fn(() => Promise.resolve({ data: {} }))
          return cible[cle]
        },
      }),
    }
  },
}))
vi.mock('../../api/crmApi', () => apiAuto())
vi.mock('../../api/stockApi', () => apiAuto())
vi.mock('../../api/parametresApi', () => apiAuto())
vi.mock('../../api/ventesApi', () => apiAuto())

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(DATE_FIGEE)
  try { window.localStorage.clear() } catch { /* stockage indisponible */ }
  if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {}
  if (!window.matchMedia) {
    window.matchMedia = vi.fn().mockImplementation((q) => ({
      matches: false, media: q, onchange: null,
      addListener: vi.fn(), removeListener: vi.fn(),
      addEventListener: vi.fn(), removeEventListener: vi.fn(), dispatchEvent: vi.fn(),
    }))
  }
  if (!globalThis.ResizeObserver) {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
  }
})

afterEach(() => {
  cleanup()
  vi.useRealTimers()
})

describe('AGNR26 — champ « Heures de pompage » retiré', () => {
  it('générateur agricole : aucun #gen-heures', async () => {
    const vue = await monter('/ventes/devis/nouveau')
    await attendreStable(vue.container, act)
    await act(async () => { fireEvent.click(await screen.findByRole('radio', { name: /Agricole/ })) })
    await attendreStable(vue.container, act)
    expect(document.getElementById('gen-hmt')).not.toBeNull()
    expect(document.getElementById('gen-heures')).toBeNull()
    expect(document.body.textContent).not.toMatch(/Heures de pompage effectives/)
  }, 60000)

  it('un brouillon ancien portant `pompeHeures` se restaure sans erreur', async () => {
    window.localStorage.setItem('taqinor:draft:devis:new', JSON.stringify({
      savedAt: '2026-10-07T10:00:00Z',
      data: { pompeHeures: '9', note: 'Brouillon ancien' },
    }))
    const vue = await monter('/ventes/devis/nouveau')
    await attendreStable(vue.container, act)
    const reprendre = [...document.querySelectorAll('button')]
      .find((b) => /Reprendre le brouillon/.test(b.textContent || ''))
    expect(reprendre).toBeTruthy()
    await act(async () => { fireEvent.click(reprendre) })
    await attendreStable(vue.container, act)
    expect(document.querySelector('textarea[placeholder^="Conditions particulières"]')?.value)
      .toBe('Brouillon ancien')
    expect(document.getElementById('gen-heures')).toBeNull()
  }, 60000)
})
