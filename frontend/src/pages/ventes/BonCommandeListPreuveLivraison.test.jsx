// AUD119 (FG51) — LA PREUVE DE LIVRAISON PART ENFIN DE L'ECRAN.
//
// `marquer-livre` lisait `signataire`, `note_pv` et le fichier `pv` depuis le
// premier jour, et savait stocker la piece jointe. Cote ecran, le thunk
// `marquerLivreBC` n'acceptait qu'un id et le bouton « Livrer » appelait
// `doAction` sans le moindre formulaire : `pv_livraison` restait donc toujours
// vide, `has_proof_of_delivery` toujours faux, et l'avertissement « vous
// facturez sans BL signe » etait permanent — un bruit que tout le monde
// ignorait, alors qu'aucun chemin produit ne permettait d'y repondre.
//
// Ces tests etaient ROUGES avant le correctif : le bouton n'ouvrait aucun
// dialogue et le corps envoye etait vide.

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'
import ventesReducer from '../../features/ventes/store/ventesSlice'

vi.mock('../../api/crmApi', () => ({
  default: { getClients: vi.fn(() => Promise.resolve({ data: [] })) },
}))
vi.mock('../../api/ventesApi', () => ({
  default: {
    getBonsCommande: vi.fn(() => Promise.resolve({ data: [] })),
    marquerLivreBC: vi.fn(),
  },
}))
vi.mock('../../features/ventes/store/ventesSlice', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, fetchBonsCommande: () => ({ type: 'ventes/fetchBonsCommande/noop' }) }
})

import ventesApi from '../../api/ventesApi'
import BonCommandeList from './BonCommandeList'

const BC = {
  id: 7,
  reference: 'BC-2026-119',
  client: 5,
  client_nom: 'Client Test',
  devis_reference: 'DEV-2026-119',
  total_ttc: '10000.00',
  date_livraison_prevue: null,
  statut: 'confirme',
  has_facture: false,
  facture_active: false,
  est_partiellement_livre: false,
  has_proof_of_delivery: false,
  reliquat_par_ligne: [],
}

function renderPage() {
  const store = configureStore({
    reducer: { ventes: ventesReducer },
    preloadedState: {
      ventes: {
        devis: [], bonsCommande: [BC], factures: [], facturesKpis: null,
        loading: false, error: null, pdfLoading: false,
      },
    },
  })
  return render(
    <Provider store={store}>
      <MemoryRouter><BonCommandeList /></MemoryRouter>
    </Provider>,
  )
}

beforeEach(() => { vi.clearAllMocks() })

describe('BonCommandeList — AUD119 preuve de livraison', () => {
  it('le bouton « Livrer » ouvre un dialogue de preuve de livraison', async () => {
    renderPage()
    fireEvent.click(screen.getByRole('button', { name: 'Livrer' }))
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByLabelText(/Signataire/)).toBeInTheDocument()
    expect(within(dialog).getByLabelText(/Bon de livraison signe/)).toBeInTheDocument()
    // Aucun appel reseau tant que le formulaire n'est pas soumis.
    expect(ventesApi.marquerLivreBC).not.toHaveBeenCalled()
  })

  it('la soumission transmet le signataire saisi', async () => {
    ventesApi.marquerLivreBC.mockResolvedValue({ data: { ...BC, statut: 'livre' } })
    renderPage()
    fireEvent.click(screen.getByRole('button', { name: 'Livrer' }))
    const dialog = await screen.findByRole('dialog')
    fireEvent.change(within(dialog).getByLabelText(/Signataire/), {
      target: { value: 'M. Alaoui' },
    })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Marquer livre' }))

    await waitFor(() => expect(ventesApi.marquerLivreBC).toHaveBeenCalledWith(
      7, expect.objectContaining({ signataire: 'M. Alaoui' })))
  })

  it('sans aucune saisie, le BC est livre sans preuve (comportement historique)', async () => {
    ventesApi.marquerLivreBC.mockResolvedValue({ data: { ...BC, statut: 'livre' } })
    renderPage()
    fireEvent.click(screen.getByRole('button', { name: 'Livrer' }))
    const dialog = await screen.findByRole('dialog')
    fireEvent.click(within(dialog).getByRole('button', { name: 'Marquer livre' }))

    await waitFor(() => expect(ventesApi.marquerLivreBC).toHaveBeenCalledWith(7, null))
  })
})
