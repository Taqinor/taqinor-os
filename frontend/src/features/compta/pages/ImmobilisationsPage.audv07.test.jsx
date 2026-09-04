import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'
import { exempleContrat } from '../../../test/fixtures/contractSamples'

/* AUDV07 / XACC16 — postage d'une dotation dérogatoire.

   Le plan fiscal se générait bien depuis cet écran (action `plan-fiscal`,
   déjà branchée) avec ses différences par exercice — mais AUCUNE ne pouvait
   être passée au grand livre : `services.poster_dotation_derogatoire` n'avait
   aucun appelant, donc la provision réglementée 1351 n'était jamais
   constituée. L'écart fiscal/comptable restait un chiffre d'écran, invisible
   du bilan.

   La charge utile du postage vient de l'exemple COMMITTÉ
   (`apps/compta/contract_samples/dotation_derogatoire_poster.json`), celui
   que `test_audv07_derogatoire_rest.py` affirme contre la vraie réponse. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

const PLAN_FISCAL = {
  id: 12,
  mode: 'degressif',
  duree_annees: 5,
  dotations_derogatoires: [
    { id: 144, annee: 2026, dotation_comptable: '20000.00',
      dotation_fiscale: '38750.00', difference: '18750.00', posted: false },
    { id: 145, annee: 2027, dotation_comptable: '20000.00',
      dotation_fiscale: '23250.00', difference: '3250.00', posted: true },
  ],
}

const mocks = vi.hoisted(() => ({
  immobilisations: vi.fn(),
  planFiscal: vi.fn(),
  posterDerogatoire: vi.fn(),
  vide: () => Promise.resolve({ data: [] }),
}))

vi.mock('../../../api/comptaApi', () => ({
  default: {
    immobilisations: {
      list: mocks.immobilisations,
      get: mocks.vide, create: mocks.vide, update: mocks.vide,
      remove: mocks.vide,
      planAmortissement: mocks.vide,
      genererPlanAmortissement: mocks.vide,
      planFiscal: mocks.planFiscal,
      genererPlanFiscal: mocks.vide,
      ceder: mocks.vide,
      depuisFactureFournisseur: mocks.vide,
      posterDotationDerogatoire: mocks.posterDerogatoire,
    },
    comptes: { list: mocks.vide },
    centresCout: { list: mocks.vide },
  },
}))

import ImmobilisationsPage from './ImmobilisationsPage.jsx'

function mount() {
  const store = configureStore({
    reducer: { auth: () => ({ role: 'admin', role_nom: null, permissions: [] }) },
  })
  return render(
    <Provider store={store}>
      <MemoryRouter initialEntries={['/']}>
        <ThemeProvider><ImmobilisationsPage /></ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

describe('ImmobilisationsPage — dotation dérogatoire (AUDV07)', () => {
  it('poste la dotation NON postée et n’en propose aucune sur celle déjà postée', async () => {
    mocks.immobilisations.mockResolvedValue({
      data: [{ id: 5, reference: 'IMM-2026-0005', libelle: 'Machine industrielle',
        categorie: 'materiel', cout: '100000.00',
        date_acquisition: '2026-01-01', statut: 'en_service' }],
    })
    mocks.planFiscal.mockResolvedValue({ data: PLAN_FISCAL })
    mocks.posterDerogatoire.mockResolvedValue({
      data: exempleContrat('compta', 'dotation_derogatoire_poster'),
    })

    mount()

    const ligne = (await screen.findAllByText('Machine industrielle'))
      .map((el) => el.closest('tr')).find(Boolean)
    await userEvent.click(
      within(ligne).getByLabelText("Plus d'actions sur la ligne"))
    await userEvent.click(await screen.findByRole(
      'menuitem', { name: /Plan fiscal/i }))

    const dialogue = await screen.findByRole('dialog')
    await waitFor(() => {
      expect(within(dialogue).getByText('2026')).toBeInTheDocument()
    })
    // Un seul exercice est postable : celui qui ne l'est pas encore.
    const boutons = within(dialogue).getAllByRole('button', { name: 'Poster' })
    expect(boutons).toHaveLength(1)

    fireEvent.click(boutons[0])
    await waitFor(() => {
      expect(mocks.posterDerogatoire).toHaveBeenCalledWith(5, 2026)
    })
  }, 30000)
})
