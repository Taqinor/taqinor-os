// AGNR21 — trois issues pour l'enregistrement : ok / PARTIEL / échec. Quand
// `PATCH etude-params` est refusé APRÈS l'écriture des lignes, l'écran reste
// sur le formulaire, le message serveur est visible dans un bandeau
// persistant et un nouvel essai ne crée jamais un second devis.
//
// Run : npx vitest run src/pages/ventes/DevisGenerator.agnrEnregistrementPartiel.test.jsx
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { act, cleanup, fireEvent, screen, waitFor } from '@testing-library/react'

import {
  DATE_FIGEE, LEAD, monter, attendreStable, DEVIS_REGISTRE,
} from './DevisGeneratorGoldenHarnais'
import { exempleContrat } from '../../test/fixtures/contractSamples'

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

const REFUS = {
  response: {
    status: 400,
    data: { detail: 'Facture(s) mensuelle(s) inférieure(s) aux lignes fixes du compteur (39,94 MAD TTC/mois).' },
  },
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

const cliquerEnregistrer = async (re) => {
  const b = [...document.querySelectorAll('button')].find((x) => re.test(x.textContent || ''))
  expect(b, `bouton ${re}`).toBeTruthy()
  await act(async () => { fireEvent.click(b) })
}

describe('AGNR21 — enregistrement partiel', () => {
  it('édition : étude refusée ⇒ formulaire conservé, bandeau persistant, aucun panneau de succès', async () => {
    const vue = await monter(`/ventes/devis/nouveau?edit=${DEVIS_REGISTRE.id}`, {
      devis: DEVIS_REGISTRE,
      avant: ({ ventesApi }) => { ventesApi.patchEtudeParams.mockRejectedValue(REFUS) },
    })
    await attendreStable(vue.container, act)
    await cliquerEnregistrer(/Enregistrer les modifications/)
    await waitFor(() => expect(vue.ventesApi.patchEtudeParams).toHaveBeenCalled())
    await attendreStable(vue.container, act)
    expect(vue.ventesApi.replaceLignesDevis).toHaveBeenCalledTimes(1)
    expect(screen.queryByText('APRES-ENREGISTREMENT')).toBeNull()
    expect(document.querySelector('form')).not.toBeNull()
    const bandeau = screen.getByTestId('reserve-enregistrement')
    expect(bandeau.textContent).toMatch(/Devis enregistré, étude non attachée : Facture\(s\) mensuelle\(s\)/)
    // Un nouvel essai réédite le même devis.
    await cliquerEnregistrer(/Enregistrer les modifications/)
    await waitFor(() => expect(vue.ventesApi.replaceLignesDevis).toHaveBeenCalledTimes(2))
    expect(vue.ventesApi.createDevisAtomic).not.toHaveBeenCalled()
  }, 60000)

  it('création : étude refusée ⇒ le nouvel essai édite le devis créé, jamais un second', async () => {
    const vue = await monter(`/ventes/devis/nouveau?lead=${LEAD.id}`, {
      avant: ({ ventesApi }) => {
        ventesApi.composerDevis.mockResolvedValue({ data: exempleContrat('ventes', 'devis_composition', 'exemple') })
        ventesApi.createDevisAtomic.mockResolvedValue({
          data: { id: 900, reference: 'DEV-202610-0900', statut: 'brouillon', updated_at: '2026-10-08T09:00:00Z' },
        })
        ventesApi.patchEtudeParams.mockRejectedValue(REFUS)
      },
    })
    await attendreStable(vue.container, act)
    await act(async () => {
      fireEvent.change(screen.getByLabelText(/Nombre de panneaux/), { target: { value: '8' } })
    })
    await act(async () => { fireEvent.click(screen.getByTestId('btn-auto-remplir')) })
    await waitFor(() => expect(vue.ventesApi.composerDevis).toHaveBeenCalled())
    await attendreStable(vue.container, act)
    await cliquerEnregistrer(/Créer le devis/)
    await waitFor(() => expect(vue.ventesApi.createDevisAtomic).toHaveBeenCalledTimes(1), { timeout: 5000 })
    await attendreStable(vue.container, act)
    expect(screen.getByTestId('reserve-enregistrement')).toBeTruthy()
    await cliquerEnregistrer(/Enregistrer les modifications/)
    await waitFor(() => expect(vue.ventesApi.replaceLignesDevis).toHaveBeenCalled())
    expect(vue.ventesApi.replaceLignesDevis.mock.calls.at(-1)[0]).toBe(900)
    expect(vue.ventesApi.createDevisAtomic).toHaveBeenCalledTimes(1)
  }, 60000)
})
