// XSAL12 — colonne « Reliquat » + dialogue de livraison partielle sur le
// Kanban des bons de commande (bc.reliquat_par_ligne / est_partiellement_livre,
// déjà sérialisés par BonCommandeSerializer). ZSAL8 — bouton PDF du BC.

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
    livrerPartielBC: vi.fn(),
    getBonCommandePdf: vi.fn(),
  },
}))
// La liste ne doit toucher aucun réseau au montage — on neutralise le thunk
// de chargement (même pattern que DevisList.test.jsx) pour garder l'état
// préchargé du store dans le test.
vi.mock('../../features/ventes/store/ventesSlice', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, fetchBonsCommande: () => ({ type: 'ventes/fetchBonsCommande/noop' }) }
})

import ventesApi from '../../api/ventesApi'
import VentesKanban from './VentesKanban'

const BC_AVEC_RELIQUAT = {
  id: 1,
  reference: 'BC-2026-001',
  client: 5,
  client_nom: 'Client Test',
  devis_reference: 'DEV-2026-001',
  total_ttc: '10000.00',
  date_livraison_prevue: null,
  statut: 'confirme',
  has_facture: false,
  est_partiellement_livre: false,
  reliquat_par_ligne: [
    { ligne_devis_id: 42, designation: 'Panneau Solaire 550W', quantite_commandee: 10, quantite_livree: 0, reliquat: 10 },
  ],
}

function makeStore(bonsCommande = []) {
  return configureStore({
    reducer: { ventes: ventesReducer },
    preloadedState: {
      ventes: { devis: [], bonsCommande, factures: [], loading: false, error: null, pdfLoading: false },
    },
  })
}

function renderPage(bonsCommande) {
  return render(
    <Provider store={makeStore(bonsCommande)}>
      <MemoryRouter><VentesKanban /></MemoryRouter>
    </Provider>,
  )
}

beforeEach(() => { vi.clearAllMocks() })

describe('VentesKanban — XSAL12 livraison partielle', () => {
  it('affiche « Livrer partiellement » pour un BC confirmé avec devis', () => {
    renderPage([BC_AVEC_RELIQUAT])
    expect(screen.getByRole('button', { name: 'Livrer partiellement' })).toBeInTheDocument()
  })

  it('le badge Reliquat affiche « Partiel » quand est_partiellement_livre est vrai', () => {
    renderPage([{ ...BC_AVEC_RELIQUAT, est_partiellement_livre: true }])
    expect(screen.getByText('Partiel')).toBeInTheDocument()
  })

  it('ouvre le dialogue et envoie la livraison saisie', async () => {
    ventesApi.livrerPartielBC.mockResolvedValue({ data: { ...BC_AVEC_RELIQUAT, id: 1 } })
    renderPage([BC_AVEC_RELIQUAT])
    fireEvent.click(screen.getByRole('button', { name: 'Livrer partiellement' }))
    const dialog = await screen.findByRole('dialog')
    fireEvent.change(within(dialog).getByLabelText(/Quantité livrée — Panneau Solaire 550W/), {
      target: { value: '4' },
    })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Enregistrer la livraison' }))
    await waitFor(() => expect(ventesApi.livrerPartielBC).toHaveBeenCalledWith(
      1, expect.objectContaining({ lignes: [{ ligne_devis: 42, quantite: '4' }] })))
  })

  it('refuse la soumission sans quantité saisie', async () => {
    renderPage([BC_AVEC_RELIQUAT])
    fireEvent.click(screen.getByRole('button', { name: 'Livrer partiellement' }))
    const dialog = await screen.findByRole('dialog')
    fireEvent.click(within(dialog).getByRole('button', { name: 'Enregistrer la livraison' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/au moins une quantité/)
    expect(ventesApi.livrerPartielBC).not.toHaveBeenCalled()
  })
})

describe('VentesKanban — ZSAL8 PDF', () => {
  it('télécharge le PDF du BC via le bouton PDF', async () => {
    ventesApi.getBonCommandePdf.mockResolvedValue({ data: new Blob(['%PDF'], { type: 'application/pdf' }) })
    URL.createObjectURL = vi.fn(() => 'blob:mock')
    URL.revokeObjectURL = vi.fn()
    renderPage([BC_AVEC_RELIQUAT])
    fireEvent.click(screen.getByRole('button', { name: 'PDF' }))
    await waitFor(() => expect(ventesApi.getBonCommandePdf).toHaveBeenCalledWith(1))
  })
})
