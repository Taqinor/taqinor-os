// AGNR24 — l'aperçu reçoit la consommation que l'écran ENREGISTRE
// (`consoEcran`, même cascade que le corps) : 12 factures de 800 MAD sans
// facture réelle ⇒ aperçu au modèle « factures » (plus le bandeau
// « Estimation… renseignez la facture réelle »), et la conso enregistrée
// est celle des 12 factures au barème (5 880 kWh).
//
// Run : npx vitest run src/pages/ventes/DevisGenerator.agnrConsoApercu.test.jsx
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { act, cleanup, fireEvent, waitFor } from '@testing-library/react'

import { DATE_FIGEE, monter, attendreStable, DEVIS_REGISTRE } from './DevisGeneratorGoldenHarnais'
import { consoAnnuelleDepuisFactures } from '../../features/ventes/solar'

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

describe('AGNR24 — la conso de l’aperçu est celle du corps enregistré', () => {
  it('12 × 800 MAD sans facture réelle ⇒ modèle « factures », conso 5 880 enregistrée', async () => {
    const vue = await monter(`/ventes/devis/nouveau?edit=${DEVIS_REGISTRE.id}`, { devis: DEVIS_REGISTRE })
    await attendreStable(vue.container, act)
    const cases = [...document.querySelectorAll('.gen-monthly-grid input')]
    for (const c of cases) {
      await act(async () => { fireEvent.change(c, { target: { value: '800' } }) })
    }
    await attendreStable(vue.container, act)
    const texte = document.body.textContent
    expect(texte).toMatch(/Facture réelle ONEE ≈/)
    expect(texte).not.toMatch(/Estimation \(production × autoconsommation × tarif moyen\)/)

    const bouton = [...document.querySelectorAll('button')]
      .find((b) => /Enregistrer les modifications/.test(b.textContent || ''))
    await act(async () => { fireEvent.click(bouton) })
    await waitFor(() => expect(vue.ventesApi.patchEtudeParams).toHaveBeenCalled(), { timeout: 5000 })
    const corps = vue.ventesApi.patchEtudeParams.mock.calls.at(-1)[1]
    const attendu = consoAnnuelleDepuisFactures(Array(12).fill(800), 'onee')
    expect(attendu).toBe(5880)
    expect(corps.conso_annuelle).toBe(attendu)
  }, 60000)
})
