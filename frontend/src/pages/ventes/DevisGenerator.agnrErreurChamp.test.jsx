// AGNR33 — un refus 400 « par champ » de l'enregistrement s'affiche sous LE
// champ et le bandeau le nomme (jamais la phrase générique) ; une saisie que
// AGNR8 normalisera est dite sous son champ (« 12,345 → 12,35 »).
//
// Run : npx vitest run src/pages/ventes/DevisGenerator.agnrErreurChamp.test.jsx
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { act, cleanup, fireEvent, screen, waitFor } from '@testing-library/react'

import { DATE_FIGEE, monter, attendreStable, DEVIS_REGISTRE } from './DevisGeneratorGoldenHarnais'

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

const MESSAGE = "Assurez-vous qu'il n'y a pas plus de 2 chiffres après la virgule."
const remise = () => document.querySelector('.gen-discount-input')

describe('AGNR33 — refus par champ et normalisations', () => {
  it('400 { remise_globale } ⇒ message sous « Réduction » et bandeau qui le nomme', async () => {
    const vue = await monter(`/ventes/devis/nouveau?edit=${DEVIS_REGISTRE.id}`, {
      devis: DEVIS_REGISTRE,
      avant: ({ ventesApi }) => {
        ventesApi.replaceLignesDevis.mockRejectedValue({
          response: { status: 400, data: { remise_globale: [MESSAGE] } },
        })
      },
    })
    await attendreStable(vue.container, act)
    const bouton = [...document.querySelectorAll('button')]
      .find((b) => /Enregistrer les modifications/.test(b.textContent || ''))
    await act(async () => { fireEvent.click(bouton) })
    await waitFor(() => expect(screen.getByTestId('erreur-champ-remise_globale').textContent).toBe(MESSAGE))
    expect(screen.getByTestId('erreur-enregistrement').textContent).toBe(`Réduction : ${MESSAGE}`)
    expect(document.body.textContent).not.toMatch(/L'enregistrement a échoué — vérifiez les champs/)
  }, 60000)

  it('« 12.345 » ⇒ note « 12,345 → 12,35 » sous le champ, et 12.35 part', async () => {
    const vue = await monter(`/ventes/devis/nouveau?edit=${DEVIS_REGISTRE.id}`, { devis: DEVIS_REGISTRE })
    await attendreStable(vue.container, act)
    await act(async () => { fireEvent.change(remise(), { target: { value: '12.345' } }) })
    expect(screen.getByTestId('note-champ-remise_globale').textContent).toBe('12,345 → 12,35')
    const bouton = [...document.querySelectorAll('button')]
      .find((b) => /Enregistrer les modifications/.test(b.textContent || ''))
    await act(async () => { fireEvent.click(bouton) })
    await waitFor(() => expect(vue.ventesApi.replaceLignesDevis).toHaveBeenCalled(), { timeout: 5000 })
    expect(vue.ventesApi.replaceLignesDevis.mock.calls.at(-1)[2].entete.remise_globale).toBe('12.35')
  }, 60000)
})
