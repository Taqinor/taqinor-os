// AGNR44 / D-AGNR-2 (a) — le curseur « Consommation diurne (%) » (aperçu local
// seulement, jamais enregistré ni relu) est retiré : le repli local prend la
// part diurne par défaut du marché et le dit. Un ancien brouillon portant
// `dayUsage` se restaure sans erreur.
//
// Run : npx vitest run src/pages/ventes/DevisGenerator.agnrPartDiurne.test.jsx
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

describe('AGNR44 — curseur « Consommation diurne » retiré', () => {
  it('résidentiel : aucun curseur, la mention « hypothèse par défaut » est là', async () => {
    const vue = await monter('/ventes/devis/nouveau')
    await attendreStable(vue.container, act)
    expect(screen.queryByTestId('curseur-part-diurne')).toBeNull()
    expect(document.body.textContent).not.toMatch(/Consommation diurne \(%\)/)
    expect(document.querySelector('input[type="range"][min="10"][max="100"]')).toBeNull()
    const mention = screen.getByTestId('part-diurne-defaut')
    expect(mention.textContent).toMatch(/hypothèse par défaut/)
  }, 60000)

  it('un brouillon ancien portant `dayUsage` se restaure sans erreur', async () => {
    window.localStorage.setItem('taqinor:draft:devis:new', JSON.stringify({
      savedAt: '2026-10-07T10:00:00Z',
      data: { dayUsage: '90', note: 'Brouillon ancien' },
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
    expect(screen.getByTestId('part-diurne-defaut').textContent).not.toMatch(/90 %/)
  }, 60000)
})
