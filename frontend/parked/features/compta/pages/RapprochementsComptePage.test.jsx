import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { toast } from '../../../ui'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'

/* PACT30 — Rapprochements de comptes de bilan (NTFIN35-37, contrôle 4 yeux).
   Le refus 403 (réviseur = préparateur) doit s'afficher TEL QUEL — jamais une
   erreur générique — c'est le comportement mesuré de
   `RapprochementCompteViewSet.valider` (apps/compta/views.py). */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  valider: vi.fn(),
  comptes: vi.fn(),
  periodes: vi.fn(),
}))

vi.mock('../../../api/comptaApi', () => ({
  default: {
    rapprochementsCompte: { list: mocks.list, valider: mocks.valider },
    comptes: { list: mocks.comptes },
    periodes: { list: mocks.periodes },
  },
}))

import RapprochementsComptePage from './RapprochementsComptePage.jsx'

function mount() {
  const store = configureStore({
    reducer: { auth: () => ({ role: 'admin', role_nom: null, permissions: [] }) },
  })
  return render(
    <Provider store={store}>
      <MemoryRouter initialEntries={['/']}>
        <ThemeProvider><RapprochementsComptePage /></ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

describe('RapprochementsComptePage — séparation des tâches (PACT30)', () => {
  it('affiche le message serveur 403 tel quel quand le réviseur = préparateur', async () => {
    mocks.comptes.mockResolvedValue({ data: [] })
    mocks.periodes.mockResolvedValue({ data: [] })
    mocks.list.mockResolvedValue({
      data: [{ id: 8, compte: 3, compte_numero: '4411', periode: 2,
        solde_gl: '1000.00', solde_justifie: '0.00', ecart: '1000.00',
        statut: 'soumis', statut_display: 'Soumis à revue', lignes: [] }],
    })
    mocks.valider.mockRejectedValueOnce({
      response: { status: 403, data: { detail: 'Séparation des tâches : le réviseur ne peut pas être le préparateur.' } },
    })
    const erreur = vi.spyOn(toast, 'error')
    mount()

    // `DataTable` ne révèle que les 2 PREMIÈRES actions de ligne ; « Valider »
    // est la 3ᵉ, donc dans le menu de débordement (patron déjà en usage dans
    // `features/paie/PaieParametres.test.jsx`).
    const ligne = (await screen.findAllByText('4411'))
      .map((el) => el.closest('tr')).find(Boolean)
    await userEvent.click(within(ligne).getByLabelText("Plus d'actions sur la ligne"))
    await userEvent.click(await screen.findByText('Valider'))

    await waitFor(() => expect(mocks.valider).toHaveBeenCalledWith(8))
    // Le 403 serveur part au toast : on prouve qu'il est relayé mot pour mot.
    expect(erreur).toHaveBeenCalledWith(
      'Séparation des tâches : le réviseur ne peut pas être le préparateur.')
  })
})
