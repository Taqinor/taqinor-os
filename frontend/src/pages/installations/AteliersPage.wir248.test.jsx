import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, screen, cleanup, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* WIR248/XMFG11 — rebut d'atelier : `declarer-rebut` et `rapport-rebuts`
   existaient côté serveur sans aucun appelant. Couvre :
   (1) le MOTIF est obligatoire — sans lui, aucun POST ;
   (2) avec motif, le POST part avec produit/quantité/motif ;
   (3) le panneau « Rebuts » rend les lignes agrégées et refiltre par période. */

const api = vi.hoisted(() => ({
  getOrdresAssemblage: vi.fn(),
  getOrdresDemontage: vi.fn(),
  getKitsAssemblage: vi.fn(),
  getDisponibiliteAssemblage: vi.fn(),
  getControleQualiteAssemblage: vi.fn(),
  getHistoriqueAssemblage: vi.fn(),
  getEtapesAssemblage: vi.fn(),
  getLignesAssemblage: vi.fn(),
  getKitStructure: vi.fn(),
  declarerRebutAssemblage: vi.fn(),
  getRapportRebuts: vi.fn(),
  bonAssemblageUrl: (id) => `/api/x/${id}/bon-pdf/`,
}))
vi.mock('../../api/installationsApi', () => ({ default: api }))

import AteliersPage from './AteliersPage'

const ORDRE = {
  id: 1, reference: 'ASM-001', kit: 3, kit_nom: 'Kit onduleur', quantite: 2,
  statut: 'en_cours', date_creation: '2026-01-01', lignes: [],
}
const LIGNE = { id: 11, ordre: 1, produit: 5, produit_nom: 'Onduleur 5kW', quantite: '2' }

function renderPage(role = 'responsable') {
  const store = configureStore({ reducer: { auth: (state = { role }) => state } })
  return render(
    <Provider store={store}>
      <MemoryRouter>
        <ThemeProvider><AteliersPage /></ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

beforeEach(() => {
  api.getOrdresAssemblage.mockResolvedValue({ data: [ORDRE] })
  api.getOrdresDemontage.mockResolvedValue({ data: [] })
  api.getKitsAssemblage.mockResolvedValue({ data: [] })
  api.getDisponibiliteAssemblage.mockResolvedValue({ data: [] })
  api.getControleQualiteAssemblage.mockResolvedValue({ data: [] })
  api.getHistoriqueAssemblage.mockResolvedValue({ data: [] })
  api.getEtapesAssemblage.mockResolvedValue({ data: [] })
  api.getLignesAssemblage.mockResolvedValue({ data: [LIGNE] })
  api.getKitStructure.mockResolvedValue({ data: { composants: [] } })
  api.declarerRebutAssemblage.mockResolvedValue({
    data: { id: 77, produit: 5, quantite: 1, motif_rebut: 'casse' },
  })
  api.getRapportRebuts.mockResolvedValue({
    data: [{
      produit_id: 5, produit_nom: 'Onduleur 5kW', quantite_totale: 3,
      motifs: { casse: 2, defaut: 1 },
    }],
  })
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

async function ouvrirRebut(user, container) {
  await waitFor(() => expect(container.querySelector('[data-dt-table]')).not.toBeNull())
  const table = within(container.querySelector('[data-dt-table]'))
  await user.click(await table.findByText('ASM-001'))
  await waitFor(() => expect(api.getLignesAssemblage).toHaveBeenCalledWith(1))
  await user.click(await screen.findByRole('button', { name: /Déclarer un rebut/ }))
  return screen.findByText('Sortie de stock typée REBUT rattachée à ASM-001.', { exact: false })
}

describe('AteliersPage — WIR248 déclaration de rebut', () => {
  it('refuse d’envoyer sans motif : le bouton reste inactif, aucun POST', async () => {
    const user = userEvent.setup()
    const { container } = renderPage()
    await ouvrirRebut(user, container)

    // Produit présélectionné (une seule ligne) + quantité saisie, mais AUCUN motif.
    await user.type(screen.getByLabelText('Quantité rebutée'), '1')
    const bouton = screen.getByRole('button', { name: /Déclarer le rebut/ })
    expect(bouton).toBeDisabled()
    await user.click(bouton)
    expect(api.declarerRebutAssemblage).not.toHaveBeenCalled()
  })

  it('POSTe le rebut une fois le motif choisi', async () => {
    const user = userEvent.setup()
    const { container } = renderPage()
    await ouvrirRebut(user, container)

    await user.type(screen.getByLabelText('Quantité rebutée'), '1')
    await user.selectOptions(screen.getByLabelText('Motif'), 'casse')
    await user.click(screen.getByRole('button', { name: /Déclarer le rebut/ }))

    await waitFor(() => expect(api.declarerRebutAssemblage).toHaveBeenCalledWith(
      1, { produit: 5, quantite: '1', motif: 'casse', note: '' }))
  })
})

describe('AteliersPage — WIR248 rapport rebuts', () => {
  it('rend les lignes agrégées et refiltre par période', async () => {
    const user = userEvent.setup()
    renderPage()
    await waitFor(() => expect(api.getOrdresAssemblage).toHaveBeenCalled())

    await user.click(screen.getByRole('radio', { name: 'Rebuts' }))
    await waitFor(() => expect(api.getRapportRebuts).toHaveBeenCalledWith({}))

    const panneau = within(await screen.findByTestId('atelier-rapport-rebuts'))
    expect(panneau.getByText('Onduleur 5kW')).toBeInTheDocument()
    expect(panneau.getByText('3')).toBeInTheDocument()
    expect(panneau.getByText(/Casse : 2/)).toBeInTheDocument()

    await user.type(panneau.getByLabelText('Du'), '2026-07-01')
    await user.type(panneau.getByLabelText('Au'), '2026-07-31')
    await user.click(panneau.getByRole('button', { name: /Filtrer/ }))
    await waitFor(() => expect(api.getRapportRebuts).toHaveBeenCalledWith(
      { date_debut: '2026-07-01', date_fin: '2026-07-31' }))
  })
})
