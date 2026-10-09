import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import authReducer from '../../features/auth/store/authSlice'
import parametresReducer from '../../features/parametres/store/parametresSlice'

/* ============================================================================
   WIR109 — XSTK13 : inventaire annuel légal FIGÉ (CGNC). LECTURE SEULE côté
   modèle ; un snapshot n'est créé QUE par l'action `figer`, jamais réécrit —
   écran admin-only.
   ========================================================================== */

vi.mock('../../api/stockApi', () => ({
  default: {
    getInventairesAnnuels: vi.fn(),
    figerInventaireAnnuel: vi.fn(),
    exportInventaireAnnuelXlsx: vi.fn(),
  },
}))

import stockApi from '../../api/stockApi'
import InventairesAnnuels from './InventairesAnnuels'

function makeStore({ role = 'admin' } = {}) {
  return configureStore({
    reducer: { auth: authReducer, parametres: parametresReducer },
    preloadedState: {
      auth: {
        user: { id: 1 }, role, role_nom: role, permissions: [],
        isAuthenticated: true, loading: false,
      },
    },
  })
}

function renderPage(store = makeStore()) {
  return render(
    <Provider store={store}>
      <MemoryRouter>
        <ThemeProvider><InventairesAnnuels /></ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

describe('InventairesAnnuels (WIR109)', () => {
  it('refuse un rôle non admin', async () => {
    stockApi.getInventairesAnnuels.mockResolvedValue({ data: [] })
    renderPage(makeStore({ role: 'responsable' }))
    expect(await screen.findByText(/Réservé à l'administrateur/)).toBeInTheDocument()
  })

  it('liste les exercices figés', async () => {
    stockApi.getInventairesAnnuels.mockResolvedValue({
      data: [{ id: 1, exercice: 2025, nb_lignes: 42, total_valeur: 150000 }],
    })

    renderPage()

    expect(await screen.findByText(/Exercice 2025/)).toBeInTheDocument()
  })

  it('fige un nouvel exercice', async () => {
    stockApi.getInventairesAnnuels.mockResolvedValue({ data: [] })
    stockApi.figerInventaireAnnuel.mockResolvedValue({ data: { id: 2, exercice: 2026 } })
    const natif = vi.spyOn(window, 'confirm')

    renderPage()
    await userEvent.click(await screen.findByRole('button', { name: /Figer un exercice/ }))

    const dialog = await screen.findByRole('dialog')
    const input = within(dialog).getByLabelText(/Exercice/)
    await userEvent.clear(input)
    await userEvent.type(input, '2026')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Figer' }))
    // ASTK231 — l'irréversibilité est confirmée par l'AlertDialog commune.
    const alerte = await screen.findByRole('alertdialog')
    expect(stockApi.figerInventaireAnnuel).not.toHaveBeenCalled()
    await userEvent.click(within(alerte).getByRole('button', { name: 'Figer' }))

    await waitFor(() => {
      expect(stockApi.figerInventaireAnnuel).toHaveBeenCalledWith({ exercice: 2026 })
    })
    expect(natif).not.toHaveBeenCalled()
    natif.mockRestore()
  })

  // ASTK203 (C-ASTK-051) — seul un exercice clos se fige : l'écran propose
  // l'année précédente et affiche le 400 « non clos » SOUS le champ.
  it("pré-remplit l'année précédente", async () => {
    stockApi.getInventairesAnnuels.mockResolvedValue({ data: [] })
    renderPage()
    await userEvent.click(await screen.findByRole('button', { name: /Figer un exercice/ }))
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByLabelText(/Exercice/)).toHaveValue(new Date().getFullYear() - 1)
  })

  it('affiche le refus « exercice non clos » sous le champ', async () => {
    const message = "L'exercice 2026 n'est pas clos (31/12/2026) : figez-le à partir du 01/01/2027."
    stockApi.getInventairesAnnuels.mockResolvedValue({ data: [] })
    stockApi.figerInventaireAnnuel.mockRejectedValue({
      response: { status: 400, data: { error: 'Données invalides.', exercice: [message] } },
    })
    renderPage()
    await userEvent.click(await screen.findByRole('button', { name: /Figer un exercice/ }))
    const dialog = await screen.findByRole('dialog')
    const input = within(dialog).getByLabelText(/Exercice/)
    await userEvent.clear(input)
    await userEvent.type(input, '2026')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Figer' }))
    await userEvent.click(within(await screen.findByRole('alertdialog')).getByRole('button', { name: 'Figer' }))
    // Sous le champ (message d'erreur du FormField), pas dans le bandeau.
    expect((await within(dialog).findByText(message)).closest('#inv-exercice-error')).not.toBeNull()
  })
})
