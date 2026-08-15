import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import { exempleContrat } from '../../test/fixtures/contractSamples'

/* WIR278 — l'onglet « Contexte SMQ (ISO 4) » n'existait pas : le contexte de
   l'organisation (ISO 4.1, singleton) et les parties intéressées (ISO 4.2,
   WIR277) étaient exposés côté serveur sans aucun écran. Charges utiles
   dérivées des contrats commités (PACT10). Réseau mocké. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
  if (typeof Element.prototype.hasPointerCapture === 'undefined') {
    Element.prototype.hasPointerCapture = () => false
  }
  if (typeof Element.prototype.scrollIntoView === 'undefined') {
    Element.prototype.scrollIntoView = () => {}
  }
})

const CONTEXTE = exempleContrat('qhse', 'contexte_organisation')
const PARTIE = {
  id: 1, partie: 'Client résidentiel', attentes: 'Prix compétitif, délais tenus',
  pertinence: 'forte', pertinence_display: 'Forte', date_creation: '2026-01-01T00:00:00Z',
}

const { empty, contexteUpdate, partieCreate } = vi.hoisted(() => ({
  empty: () => Promise.resolve({ data: [] }),
  contexteUpdate: vi.fn(() => Promise.resolve({ data: {} })),
  partieCreate: vi.fn(() => Promise.resolve({ data: { id: 2 } })),
}))

vi.mock('../../api/qhseApi', () => ({
  default: {
    evaluationsRisque: { list: empty },
    risquesOpportunites: { list: empty, revuesDues: empty },
    permisTravail: { list: empty },
    consignationsLoto: { list: empty },
    inductionsSecurite: { list: empty },
    plansUrgence: { list: empty },
    secouristes: { list: empty },
    exercicesUrgence: { list: empty },
    incidents: { list: empty, notificationsEnRetard: empty },
    declarationsCnss: { list: empty },
    analysesIncident: { list: empty },
    observationsSecurite: { list: empty },
    liensSignalement: { list: empty },
    signalementsPublics: { list: empty },
    contexteOrganisation: {
      get: () => Promise.resolve({ data: exempleContrat('qhse', 'contexte_organisation') }),
      update: (...a) => contexteUpdate(...a),
    },
    partiesInteressees: {
      list: vi.fn(() => Promise.resolve({ data: [PARTIE] })),
      create: (...a) => partieCreate(...a),
    },
  },
}))

vi.mock('../../ui', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, toast: { success: vi.fn(), error: vi.fn() } }
})

import Risques from './Risques'

function withProviders(ui) {
  return render(<MemoryRouter><ThemeProvider>{ui}</ThemeProvider></MemoryRouter>)
}

beforeEach(() => { vi.clearAllMocks() })

describe('Risques — Contexte SMQ (ISO 4) (WIR278)', () => {
  it('affiche le SWOT et le périmètre du contrat, et la partie intéressée', async () => {
    const user = userEvent.setup()
    withProviders(<Risques />)
    await user.click(await screen.findByRole('tab', { name: 'Contexte SMQ (ISO 4)' }))

    expect(await screen.findByLabelText('Analyse SWOT')).toHaveValue(CONTEXTE.swot)
    expect(screen.getByLabelText('Périmètre du SMQ')).toHaveValue(CONTEXTE.perimetre_smq)
    expect(await screen.findByText('Client résidentiel')).toBeTruthy()
  })

  it('enregistre le contexte modifié via PUT', async () => {
    const user = userEvent.setup()
    withProviders(<Risques />)
    await user.click(await screen.findByRole('tab', { name: 'Contexte SMQ (ISO 4)' }))
    await screen.findByLabelText('Analyse SWOT')

    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))

    await waitFor(() => expect(contexteUpdate).toHaveBeenCalledWith(
      expect.objectContaining({ swot: CONTEXTE.swot, perimetre_smq: CONTEXTE.perimetre_smq }),
    ))
  })

  it('crée une partie intéressée de bout en bout', async () => {
    const user = userEvent.setup()
    withProviders(<Risques />)
    await user.click(await screen.findByRole('tab', { name: 'Contexte SMQ (ISO 4)' }))

    await user.click(await screen.findByRole('button', { name: /Nouvelle partie intéressée/ }))
    await user.type(await screen.findByLabelText('Partie'), 'Sous-traitant électricité')
    await user.click(screen.getByRole('button', { name: 'Créer' }))

    await waitFor(() => expect(partieCreate).toHaveBeenCalledWith(
      expect.objectContaining({ partie: 'Sous-traitant électricité', pertinence: 'moyenne' }),
    ))
  })
})
