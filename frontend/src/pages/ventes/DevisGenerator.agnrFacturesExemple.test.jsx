// AGNR13 — une facture mensuelle d'EXEMPLE ne part jamais : chaque case du
// détail mensuel porte sa provenance (exemple | dérivée | tapée) ; tant
// qu'une case est « exemple », `factures_mensuelles_reelles` ne part pas et
// les mois non saisis sont nommés sous la carte. Écran RÉEL monté, corps lu
// sur le serveur factice (jamais un espion sur un setter).
//
// Run : npx vitest run src/pages/ventes/DevisGenerator.agnrFacturesExemple.test.jsx
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { act, cleanup, fireEvent, waitFor } from '@testing-library/react'

import {
  DATE_FIGEE, monter, attendreStable, DEVIS_REGISTRE, DEVIS_ENVOYE_LES_DEUX,
} from './DevisGeneratorGoldenHarnais'

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

const cases = () => [...document.querySelectorAll('.gen-monthly-grid input')]
const taper = async (el, v) => { await act(async () => { fireEvent.change(el, { target: { value: v } }) }) }

async function enregistrer(vue) {
  const bouton = [...document.querySelectorAll('button')]
    .find((b) => /Enregistrer les modifications/.test(b.textContent || ''))
  await act(async () => { fireEvent.click(bouton) })
  await waitFor(() => expect(vue.ventesApi.replaceLignesDevis).toHaveBeenCalled(), { timeout: 5000 })
  await attendreStable(vue.container, act)
  // L'étude part par la FUSION (`PATCH etude-params`) après replace-lines.
  const [, , extra] = vue.ventesApi.replaceLignesDevis.mock.calls.at(-1)
  const fusion = vue.ventesApi.patchEtudeParams.mock.calls.at(-1)?.[1] || {}
  return { ...(extra?.etude_params || {}), ...fusion }
}

describe('AGNR13 — jamais une facture mensuelle d’exemple', () => {
  it('Janvier seul tapé ⇒ aucune série envoyée, les 11 autres mois sont nommés', async () => {
    const vue = await monter(`/ventes/devis/nouveau?edit=${DEVIS_REGISTRE.id}`, { devis: DEVIS_REGISTRE })
    await attendreStable(vue.container, act)
    expect(cases()).toHaveLength(12)
    await taper(cases()[0], '900')
    const message = document.querySelector('[data-testid="mois-non-saisis"]')
    expect(message?.textContent).toMatch(/Fév/)
    expect(message?.textContent).not.toMatch(/Jan,/)
    const etude = await enregistrer(vue)
    expect(etude).not.toHaveProperty('factures_mensuelles_reelles')
  }, 60000)

  it('les 12 mois tapés ⇒ la série part avec les 12 valeurs tapées', async () => {
    const vue = await monter(`/ventes/devis/nouveau?edit=${DEVIS_REGISTRE.id}`, { devis: DEVIS_REGISTRE })
    await attendreStable(vue.container, act)
    const valeurs = [900, 850, 800, 700, 650, 900, 1200, 1300, 1000, 750, 700, 850]
    for (let i = 0; i < 12; i += 1) await taper(cases()[i], String(valeurs[i]))
    expect(document.querySelector('[data-testid="mois-non-saisis"]')).toBeNull()
    const etude = await enregistrer(vue)
    expect(etude.factures_mensuelles_reelles).toEqual(valeurs)
  }, 60000)

  it('vider une case ne la rend pas « tapée »', async () => {
    const vue = await monter(`/ventes/devis/nouveau?edit=${DEVIS_REGISTRE.id}`, { devis: DEVIS_REGISTRE })
    await attendreStable(vue.container, act)
    for (let i = 0; i < 12; i += 1) await taper(cases()[i], '600')
    await taper(cases()[3], '')
    expect(document.querySelector('[data-testid="mois-non-saisis"]')?.textContent).toMatch(/Avr/)
    const etude = await enregistrer(vue)
    expect(etude).not.toHaveProperty('factures_mensuelles_reelles')
  }, 60000)

  it('série relue d’un devis (12 mois) ⇒ ré-enregistrée telle quelle sans retouche', async () => {
    const vue = await monter(`/ventes/devis/nouveau?edit=${DEVIS_ENVOYE_LES_DEUX.id}`, { devis: DEVIS_ENVOYE_LES_DEUX })
    await attendreStable(vue.container, act)
    const etude = await enregistrer(vue)
    expect(etude.factures_mensuelles_reelles)
      .toEqual(DEVIS_ENVOYE_LES_DEUX.etude_params.factures_mensuelles_reelles)
  }, 60000)
})
