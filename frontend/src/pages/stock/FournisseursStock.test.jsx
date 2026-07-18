import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import authReducer from '../../features/auth/store/authSlice'

/* ============================================================================
   WIR26 — statut de blocage fournisseur (XPUR4) + motif_blocage exposés sur la
   fiche (jusqu'ici seul un accès direct à la base pouvait les changer, alors
   que le blocage BCF/paiement est déjà appliqué et testé côté serveur —
   apps/stock/services.py:check_fournisseur_statut_commande/paiement).
   (ResizeObserver/hasPointerCapture/scrollIntoView requis par Radix Select
   sont déjà polyfillés globalement — src/test/setup.js — aucun stub local ici.)
   ========================================================================== */

vi.mock('../../api/stockApi', () => ({
  default: {
    getFournisseurs: vi.fn(() => Promise.resolve({
      data: [
        { id: 1, nom: 'Actif SARL', statut: 'actif', nb_produits: 2, nb_bons_commande: 1 },
        {
          id: 2, nom: 'Bloqué Commandes SARL', statut: 'bloque_commandes',
          motif_blocage: 'Litige qualité', nb_produits: 0, nb_bons_commande: 0,
        },
      ],
    })),
    createFournisseur: vi.fn(() => Promise.resolve({ data: {} })),
    updateFournisseur: vi.fn(() => Promise.resolve({ data: {} })),
    deleteFournisseur: vi.fn(() => Promise.resolve({})),
    performanceFournisseur: vi.fn(() => Promise.resolve({ data: {} })),
  },
}))

import stockApi from '../../api/stockApi'
import FournisseursStock from './FournisseursStock'

function makeStore({ role = 'admin', permissions = ['stock_modifier', 'stock_voir'] } = {}) {
  return configureStore({
    reducer: { auth: authReducer },
    preloadedState: {
      auth: {
        user: { id: 1 }, role, role_nom: role, permissions,
        isAuthenticated: true, loading: false,
      },
    },
  })
}

function renderPage(store = makeStore()) {
  return render(
    <Provider store={store}>
      <MemoryRouter>
        <ThemeProvider><FournisseursStock /></ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

describe('FournisseursStock — statut de blocage (WIR26)', () => {
  it('affiche le statut de blocage de chaque fournisseur dans la liste', async () => {
    renderPage()
    const grid = await screen.findByRole('grid', { name: 'Fournisseurs' })

    expect(within(grid).getByText('Actif SARL')).toBeInTheDocument()
    expect(within(grid).getByText('Bloqué (commandes)')).toBeInTheDocument()
  })

  it('éditer le fournisseur bloqué pré-remplit statut + motif_blocage', async () => {
    renderPage()
    const grid = await screen.findByRole('grid', { name: 'Fournisseurs' })
    const row = within(grid).getByText('Bloqué Commandes SARL').closest('tr')

    await userEvent.click(within(row).getByRole('button', { name: 'Modifier' }))

    expect(await screen.findByText('Fournisseur — Bloqué Commandes SARL')).toBeInTheDocument()
    // motif_blocage est un <textarea> contrôlé : sa valeur n'est pas un nœud
    // texte enfant (getByText ne la trouverait pas) — getByDisplayValue.
    expect(screen.getByDisplayValue('Litige qualité')).toBeInTheDocument()
  })

  it('rebasculer un fournisseur bloqué en actif envoie statut=actif au serveur', async () => {
    renderPage()
    const grid = await screen.findByRole('grid', { name: 'Fournisseurs' })
    const row = within(grid).getByText('Bloqué Commandes SARL').closest('tr')

    await userEvent.click(within(row).getByRole('button', { name: 'Modifier' }))
    const dialog = await screen.findByRole('dialog')

    await userEvent.click(within(dialog).getByRole('combobox'))
    await userEvent.click(await screen.findByRole('option', { name: 'Actif' }))
    await userEvent.click(within(dialog).getByRole('button', { name: 'Enregistrer' }))

    await waitFor(() => expect(stockApi.updateFournisseur).toHaveBeenCalledWith(
      2, expect.objectContaining({ statut: 'actif' }),
    ))
  })
})
