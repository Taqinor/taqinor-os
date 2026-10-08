// AGNR17 — les factures repartent d'un état VIDE à chaque changement de lead,
// et aucun pré-remplissage (lead, profil de site, frappe hiver/été)
// n'écrase une facture TAPÉE ou STOCKÉE sans geste. Écran RÉEL monté, serveur
// factice aux formes réelles ; assertions sur les champs affichés.
//
// Run : npx vitest run src/pages/ventes/DevisGenerator.agnrFacturesLead.test.jsx
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { act, cleanup, fireEvent, waitFor } from '@testing-library/react'

import {
  DATE_FIGEE, LEAD, CLIENT, monter, attendreStable, DEVIS_ENVOYE_LES_DEUX,
} from './DevisGeneratorGoldenHarnais'
import { DEFAULT_MONTHLY_BILLS } from '../../features/ventes/solar'

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

const LEAD_A = { ...LEAD, id: 81, nom: 'Alami', prenom: 'A', facture_hiver: '2000' }
const LEAD_B = { ...LEAD, id: 82, nom: 'Bennis', prenom: 'B', facture_hiver: null, conso_mensuelle_kwh: null }

const hiver = () => document.getElementById('gen-hiver')?.value
const mois = () => [...document.querySelectorAll('.gen-monthly-grid input')].map((i) => Number(i.value))
const taper = async (el, v) => { await act(async () => { fireEvent.change(el, { target: { value: v } }) }) }
const choisirLead = async (id) => {
  const natif = document.getElementById('gen-lead')?.parentElement?.querySelector('select')
  await taper(natif, String(id))
}

describe('AGNR17 — factures et pré-remplissages', () => {
  it('lead A (facture 2 000) puis lead B (aucune) ⇒ factures repartent de vide', async () => {
    const vue = await monter('/ventes/devis/nouveau', { leads: [LEAD_A, LEAD_B] })
    await attendreStable(vue.container, act)
    await choisirLead(LEAD_A.id)
    await attendreStable(vue.container, act)
    expect(hiver()).toBe('2000')
    await choisirLead(LEAD_B.id)
    await attendreStable(vue.container, act)
    expect(hiver()).toBe('')
    expect(mois()).toEqual(DEFAULT_MONTHLY_BILLS)
    // Provenance « exemple » (AGNR13) : aucun mois saisi n'est annoncé.
    expect(document.querySelector('[data-testid="mois-non-saisis"]')).toBeNull()
  }, 60000)

  it('hiver tapé 1 500 puis profil de site 900 ⇒ 1 500 gardé, avis non bloquant', async () => {
    let repondre
    const vue = await monter(`/ventes/devis/nouveau?client=${CLIENT.id}`, {
      avant: ({ ventesApi }) => {
        ventesApi.getPrefillSite.mockImplementation(() => new Promise((r) => { repondre = r }))
      },
    })
    await attendreStable(vue.container, act)
    await taper(document.getElementById('gen-hiver'), '1500')
    expect(typeof repondre).toBe('function')
    await act(async () => {
      repondre({ data: { profil: { type_installation: 'residentiel', facture_hiver: '900' } } })
    })
    await attendreStable(vue.container, act)
    expect(hiver()).toBe('1500')
    expect(document.querySelector('[data-testid="avis-factures"]')?.textContent)
      .toMatch(/Profil de site non appliqué aux factures déjà saisies/)
  }, 60000)

  it('édition : taper « Facture Hiver » ne remplace pas les 12 factures stockées', async () => {
    const vue = await monter(`/ventes/devis/nouveau?edit=${DEVIS_ENVOYE_LES_DEUX.id}`, { devis: DEVIS_ENVOYE_LES_DEUX })
    await attendreStable(vue.container, act)
    const avant = mois()
    expect(avant).toEqual(DEVIS_ENVOYE_LES_DEUX.etude_params.factures_mensuelles_reelles)
    await taper(document.getElementById('gen-hiver'), '1000')
    await attendreStable(vue.container, act)
    expect(mois()).toEqual(avant)
    // Le geste explicite « Estimer 12 mois » les remplace.
    const estimer = [...document.querySelectorAll('button')].find((b) => /Estimer 12 mois/.test(b.textContent || ''))
    await act(async () => { fireEvent.click(estimer) })
    await waitFor(() => expect(mois()[0]).not.toBe(avant[0]))
  }, 60000)
})
