// AGNR14 — la « Facture réelle (MAD/mois) » est inversée au barème COMPLET
// (lignes fixes + TPPAN comprises), comme les 12 factures et le serveur :
// 150 MAD/mois ONEE ⇒ 1 282 kWh/an affichés ET enregistrés, jamais 1 800.
//
// Valeurs du jumeau serveur `kwh_from_bill(m, 'onee', facture_totale=True)
// × 12`, figées telles que relevées par la sonde V_VA q2/p3 de l'audit
// (C-AGNR-002) : 150 → 1 282, 800 → 5 880, 1 500 → 10 057 kWh/an.
//
// Run : npx vitest run src/pages/ventes/DevisGenerator.agnrFactureReelle.test.jsx
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { act, cleanup, fireEvent, waitFor } from '@testing-library/react'

import { DATE_FIGEE, monter, attendreStable, DEVIS_REGISTRE } from './DevisGeneratorGoldenHarnais'
import { formatNumber } from '../../lib/format'

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

const consoAffichee = () => {
  const label = [...document.querySelectorAll('label')]
    .find((l) => /Consommation annuelle dérivée/.test(l.textContent || ''))
  return label?.parentElement?.querySelector('.gen-kwp')?.textContent ?? ''
}

describe('AGNR14 — facture réelle inversée au barème complet', () => {
  it.each([[150, 1282], [800, 5880], [1500, 10057]])(
    '%s MAD/mois ONEE ⇒ %s kWh/an affichés', async (mad, kwh) => {
      const vue = await monter(`/ventes/devis/nouveau?edit=${DEVIS_REGISTRE.id}`, { devis: DEVIS_REGISTRE })
      await attendreStable(vue.container, act)
      await act(async () => {
        fireEvent.change(document.getElementById('gen-realbill'), { target: { value: String(mad) } })
      })
      expect(consoAffichee()).toBe(`${formatNumber(kwh)} kWh/an`)
    }, 60000)

  it('150 MAD/mois ⇒ conso_annuelle enregistrée = 1 282', async () => {
    const vue = await monter(`/ventes/devis/nouveau?edit=${DEVIS_REGISTRE.id}`, { devis: DEVIS_REGISTRE })
    await attendreStable(vue.container, act)
    await act(async () => {
      fireEvent.change(document.getElementById('gen-realbill'), { target: { value: '150' } })
    })
    const bouton = [...document.querySelectorAll('button')]
      .find((b) => /Enregistrer les modifications/.test(b.textContent || ''))
    await act(async () => { fireEvent.click(bouton) })
    await waitFor(() => expect(vue.ventesApi.patchEtudeParams).toHaveBeenCalled(), { timeout: 5000 })
    const corps = vue.ventesApi.patchEtudeParams.mock.calls.at(-1)[1]
    expect(corps.conso_annuelle).toBe(1282)
  }, 60000)
})
