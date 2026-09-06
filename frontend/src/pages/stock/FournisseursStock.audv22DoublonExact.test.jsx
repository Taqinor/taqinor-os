import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import authReducer from '../../features/auth/store/authSlice'

/* AUDV22 (DRAFT165-123/124, ARC20) — recherche EXACTE anti-doublon par email
   AVANT la création d'un Fournisseur (le formulaire ne porte pas d'ICE). Un
   premier submit qui trouve un tiers déjà porteur de cet email affiche un
   avertissement et REFUSE de créer ; le second submit (mêmes valeurs) passe. */

vi.mock('../../api/stockApi', () => ({
  default: {
    getFournisseurs: vi.fn(() => Promise.resolve({ data: [] })),
    createFournisseur: vi.fn(() => Promise.resolve({ data: { id: 9 } })),
    getCategoriesFournisseur: vi.fn(() => Promise.resolve({ data: [] })),
  },
}))
vi.mock('../../api/tiersApi', () => ({
  default: { verifierDoublon: vi.fn() },
}))

import stockApi from '../../api/stockApi'
import tiersApi from '../../api/tiersApi'
import FournisseursStock from './FournisseursStock'

afterEach(() => { cleanup(); vi.clearAllMocks() })

function makeStore() {
  return configureStore({
    reducer: { auth: authReducer },
    preloadedState: {
      auth: {
        user: { id: 1 }, role: 'admin', role_nom: 'admin',
        permissions: ['stock_modifier', 'stock_voir'],
        isAuthenticated: true, loading: false,
      },
    },
  })
}

function renderPage() {
  return render(
    <Provider store={makeStore()}>
      <MemoryRouter>
        <ThemeProvider><FournisseursStock /></ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

describe('FournisseursStock — anti-doublon exact email à la création (AUDV22)', () => {
  it('un email déjà porté par un tiers affiche un avertissement et refuse le premier submit', async () => {
    tiersApi.verifierDoublon.mockResolvedValue({
      data: { ice_matches: [], email_matches: [{ id: 3, nom: 'Fournisseur Existant', roles: { fournisseur: true } }] },
    })
    renderPage()
    await screen.findByRole('grid', { name: 'Fournisseurs' })

    await userEvent.click(screen.getAllByRole('button', { name: 'Nouveau fournisseur' })[0])
    const dialog = await screen.findByRole('dialog')
    await userEvent.type(within(dialog).getByRole('textbox', { name: 'Nom' }), 'Nouveau Fournisseur')
    await userEvent.type(within(dialog).getByLabelText('Email'), 'existant@example.ma')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Enregistrer' }))

    await waitFor(() => expect(tiersApi.verifierDoublon).toHaveBeenCalledWith({ email: 'existant@example.ma' }))
    expect(await within(dialog).findByTestId('fou-dup-warning')).toHaveTextContent('Fournisseur Existant')
    expect(stockApi.createFournisseur).not.toHaveBeenCalled()
  })

  it('le second submit crée malgré le doublon signalé', async () => {
    tiersApi.verifierDoublon.mockResolvedValue({
      data: { ice_matches: [], email_matches: [{ id: 3, nom: 'Fournisseur Existant', roles: { fournisseur: true } }] },
    })
    renderPage()
    await screen.findByRole('grid', { name: 'Fournisseurs' })

    await userEvent.click(screen.getAllByRole('button', { name: 'Nouveau fournisseur' })[0])
    const dialog = await screen.findByRole('dialog')
    await userEvent.type(within(dialog).getByRole('textbox', { name: 'Nom' }), 'Nouveau Fournisseur')
    await userEvent.type(within(dialog).getByLabelText('Email'), 'existant@example.ma')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Enregistrer' }))
    await within(dialog).findByTestId('fou-dup-warning')

    await userEvent.click(within(dialog).getByRole('button', { name: 'Enregistrer' }))
    await waitFor(() => expect(stockApi.createFournisseur).toHaveBeenCalledTimes(1))
    expect(tiersApi.verifierDoublon).toHaveBeenCalledTimes(1)
  })

  it('sans doublon, le premier submit crée directement', async () => {
    tiersApi.verifierDoublon.mockResolvedValue({
      data: { ice_matches: [], email_matches: [] },
    })
    renderPage()
    await screen.findByRole('grid', { name: 'Fournisseurs' })

    await userEvent.click(screen.getAllByRole('button', { name: 'Nouveau fournisseur' })[0])
    const dialog = await screen.findByRole('dialog')
    await userEvent.type(within(dialog).getByRole('textbox', { name: 'Nom' }), 'Fournisseur Propre')
    await userEvent.type(within(dialog).getByLabelText('Email'), 'propre@example.ma')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Enregistrer' }))

    await waitFor(() => expect(stockApi.createFournisseur).toHaveBeenCalledTimes(1))
    expect(screen.queryByTestId('fou-dup-warning')).not.toBeInTheDocument()
  })
})
