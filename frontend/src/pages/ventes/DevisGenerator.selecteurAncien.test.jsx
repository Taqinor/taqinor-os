// ALEA40 — les sélecteurs client et lead du générateur ne s'arrêtent plus aux
// 50 plus récents : un serveur factice applique la VRAIE pagination DRF (50
// par page, plus récents d'abord) ; le lead le plus ancien est proposé dans
// le sélecteur et le client le plus ancien (`?client=`) est résolu.
//
// Run : npx vitest run src/pages/ventes/DevisGenerator.selecteurAncien.test.jsx
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { act, cleanup, waitFor } from '@testing-library/react'

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

// 60 enregistrements, id 60 = le plus récent, id 1 = le plus ancien.
const LEADS = Array.from({ length: 60 }, (_, k) => ({
  id: 60 - k, nom: `Lead${60 - k}`, prenom: '', societe: '', facture_hiver: null,
}))
const CLIENTS = Array.from({ length: 60 }, (_, k) => ({
  id: 60 - k, nom: `Client${60 - k}`, adresse: `Adresse ${60 - k}`, telephone: '',
}))

// Pagination DRF (`core/pagination.py` : 50 par page) : sans `page`, page 1.
const paginer = (items) => (params) => {
  const page = Number(params?.page) || 1
  const results = items.slice((page - 1) * 50, page * 50)
  return Promise.resolve({
    data: { count: items.length, next: page * 50 < items.length ? `?page=${page + 1}` : null, results },
  })
}

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

const avecServeurPagine = ({ crmApi }) => {
  crmApi.getLeads.mockImplementation(paginer(LEADS))
  crmApi.getClients.mockImplementation(paginer(CLIENTS))
}

describe('ALEA40 — sélecteurs client et lead au-delà des 50 plus récents', () => {
  it('le lead le plus ancien (hors page 1) est proposé dans le sélecteur', async () => {
    const vue = await monter('/ventes/devis/nouveau', { avant: avecServeurPagine })
    await waitFor(() => expect(vue.crmApi.getLeads).toHaveBeenCalledWith({ page: 2 }))
    await attendreStable(vue.container, act)
    const natif = document.getElementById('gen-lead')?.parentElement?.querySelector('select')
    expect(natif, 'select natif du sélecteur de lead').toBeTruthy()
    const valeurs = [...natif.querySelectorAll('option')].map((o) => o.value)
    expect(valeurs).toContain('1')
    expect(valeurs).toContain('60')
  }, 60000)

  it('?client=<le plus ancien> est résolu (adresse affichée)', async () => {
    const vue = await monter('/ventes/devis/nouveau?client=1', { avant: avecServeurPagine })
    await waitFor(() => expect(vue.crmApi.getClients).toHaveBeenCalledWith({ page: 2 }))
    await attendreStable(vue.container, act)
    expect(document.getElementById('gen-adresse')?.value).toBe('Adresse 1')
  }, 60000)
})
