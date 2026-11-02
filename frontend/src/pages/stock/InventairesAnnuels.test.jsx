import { describe, it, expect, vi } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { makeAuthStore, renderStockPage } from './stockPage.testHelpers.jsx'
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
    getValorisationADate: vi.fn(),
  },
}))

import stockApi from '../../api/stockApi'
import InventairesAnnuels from './InventairesAnnuels'

const makeStore = (o) => makeAuthStore({ permissions: [], reducers: { parametres: parametresReducer }, ...o })

const renderPage = (store = makeStore()) => renderStockPage(InventairesAnnuels, store)

describe('InventairesAnnuels (WIR109)', () => {
  it('refuse un rôle non admin', async () => {
    stockApi.getInventairesAnnuels.mockResolvedValue({ data: [] })
    renderPage(makeStore({ role: 'responsable' }))
    expect(await screen.findByText(/Réservé à l'administrateur/)).toBeInTheDocument()
  })

  it('valorise le stock à une date passée (ENF15)', async () => {
    stockApi.getInventairesAnnuels.mockResolvedValue({ data: [] })
    stockApi.getValorisationADate.mockResolvedValue({
      data: {
        date: '2026-10-30', total: '1000.00',
        lignes: [{ produit_id: 1, sku: 'PAN-1', designation: 'Panneau 550W', quantite: 10,
          cout_moyen: '100.00', valeur: '1000.00', source: 'cmp' }],
      },
    })
    renderPage()
    const champ = await screen.findByLabelText('Date')
    await userEvent.clear(champ)
    await userEvent.type(champ, '2026-10-30')
    await userEvent.click(screen.getByRole('button', { name: 'Valoriser' }))
    const grille = await screen.findByRole('grid', { name: 'Valorisation du stock à une date' })
    expect(within(grille).getByText('Panneau 550W')).toBeInTheDocument()
    expect(stockApi.getValorisationADate).toHaveBeenCalledWith('2026-10-30')
  })

  it('ne propose pas la valorisation sans le droit prix d\'achat (ENF15)', async () => {
    stockApi.getInventairesAnnuels.mockResolvedValue({ data: [] })
    // Admin à rôle fin SANS `prix_achat_voir` : coûts d'achat jamais affichés.
    renderPage(makeStore({ permissions: ['stock_voir'] }))
    await screen.findByText(/Aucun exercice figé/)
    expect(screen.queryByRole('button', { name: 'Valoriser' })).toBeNull()
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
