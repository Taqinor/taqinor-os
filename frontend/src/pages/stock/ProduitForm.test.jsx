import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* ============================================================================
   PACT143 — Description commerciale d'un produit.
   ----------------------------------------------------------------------------
   NTAI13 (`apps/ai_governance`) livrait déjà `POST /ai/description-produit/`
   — brouillon FR + variante courte, VALIDÉS avant toute écriture, avec une
   liste blanche de champs qui empêche `prix_achat` d'être transmis au
   fournisseur (règle du dépôt, testée côté backend). Vérifie que
   `ProduitForm.jsx` (a) propose ce bouton SEULEMENT en édition (un produit
   pas encore créé n'a pas de `produit_id`), (b) affiche brouillon + variante
   courte dans un dialogue de validation, et (c) n'écrit RIEN tant que
   « Utiliser cette description » n'a pas été cliqué — puis remplit
   uniquement le champ `description` du formulaire (la sauvegarde réelle
   reste le bouton « Enregistrer »/« Mettre à jour » existant). */

const { apiPost, apiGet } = vi.hoisted(() => ({
  apiPost: vi.fn(),
  apiGet: vi.fn(() => Promise.resolve({ data: [] })),
}))

vi.mock('../../api/axios', () => ({
  default: { get: (...args) => apiGet(...args), post: (...args) => apiPost(...args) },
}))

// Mocké séparément : `PrixFournisseursSection` (montée en édition) appelle
// `stockApi.getProduitPrixFournisseurs` au montage — hors périmètre PACT143.
vi.mock('../../api/stockApi', () => ({
  default: {
    getProduitPrixFournisseurs: () => Promise.resolve({ data: [] }),
    // PVOND — la section « Fiche technique » lit la fiche au montage en édition.
    getFichesTechniques: () => Promise.resolve({ data: [] }),
    comparerFournisseurs: () => Promise.resolve({ data: [] }),
    // NTSCM26 — colonne TCO additionnelle du panneau « Comparer fournisseurs ».
    comparerTcoFournisseurs: () => Promise.resolve({ data: { fournisseurs: [] } }),
    createPrixFournisseur: () => Promise.resolve({ data: {} }),
    updatePrixFournisseur: () => Promise.resolve({ data: {} }),
    deletePrixFournisseur: () => Promise.resolve({ data: {} }),
    uploadProduitImage: () => Promise.resolve({ data: {} }),
  },
}))

import ProduitForm from './ProduitForm.jsx'

const store = configureStore({
  reducer: {
    auth: (s = { role: 'admin', role_nom: 'Directeur', permissions: [] }) => s,
    stock: (s = { categories: [], fournisseurs: [], produits: [] }) => s,
  },
})

function wrapper({ children }) {
  return (
    <Provider store={store}>
      <MemoryRouter><ThemeProvider>{children}</ThemeProvider></MemoryRouter>
    </Provider>
  )
}

const PRODUIT = {
  id: 7, nom: 'Onduleur Deye 8 kW', sku: 'OND-DEYE-8K', marque: 'Deye',
  description: '', prix_vente: '12345.67', prix_achat: '7777.77', tva: 20,
  quantite_stock: 5, seuil_alerte: 1, categorie: null, fournisseur: null,
}

beforeEach(() => {
  vi.clearAllMocks()
  apiGet.mockResolvedValue({ data: [] })
})

function renderEdit(over = {}) {
  return render(
    <ProduitForm produit={{ ...PRODUIT, ...over }} onClose={() => {}} onSaved={() => {}} />,
    { wrapper },
  )
}

function renderCreate() {
  return render(<ProduitForm produit={null} onClose={() => {}} onSaved={() => {}} />, { wrapper })
}

describe('ProduitForm — brouillon de description IA (PACT143)', () => {
  it('propose le bouton « Générer avec l’IA » SEULEMENT en édition', async () => {
    renderCreate()
    await screen.findByText('Nouveau produit')
    expect(screen.queryByRole('button', { name: /Générer avec l.IA/ })).not.toBeInTheDocument()
  })

  it('affiche le bouton en édition, où le produit a déjà un id', async () => {
    renderEdit()
    await screen.findByText(/Éditer/)
    expect(screen.getByRole('button', { name: /Générer avec l.IA/ })).toBeInTheDocument()
  })

  it('génère un brouillon + sa variante courte, proposés à la validation — RIEN n’est écrit avant', async () => {
    apiPost.mockResolvedValue({
      data: {
        description: 'Onduleur hybride robuste, garantie 10 ans.',
        description_courte: 'Onduleur hybride Deye.',
        applique: false,
      },
    })
    renderEdit()
    await screen.findByText(/Éditer/)

    fireEvent.click(screen.getByRole('button', { name: /Générer avec l.IA/ }))

    await waitFor(() => expect(apiPost).toHaveBeenCalledWith(
      '/ai/description-produit/', { produit_id: 7 },
    ))

    // Le brouillon est affiché dans un dialogue de VALIDATION...
    const descField = await screen.findByLabelText('Description proposée')
    expect(descField).toHaveValue('Onduleur hybride robuste, garantie 10 ans.')
    expect(screen.getByLabelText('Variante courte')).toHaveValue('Onduleur hybride Deye.')

    // ...et le champ `description` DU FORMULAIRE reste vide tant que
    // l'utilisateur n'a pas cliqué « Utiliser cette description ».
    expect(document.getElementById('pf-desc')).toHaveValue('')

    fireEvent.click(screen.getByRole('button', { name: 'Utiliser cette description' }))

    await waitFor(() => expect(document.getElementById('pf-desc'))
      .toHaveValue('Onduleur hybride robuste, garantie 10 ans.'))
    // Le dialogue de validation se ferme après application.
    expect(screen.queryByLabelText('Description proposée')).not.toBeInTheDocument()
  })

  it('« Fermer » le dialogue de validation n’écrit rien dans le formulaire', async () => {
    apiPost.mockResolvedValue({
      data: { description: 'Brouillon jamais voulu.', description_courte: 'Court.', applique: false },
    })
    renderEdit()
    await screen.findByText(/Éditer/)

    fireEvent.click(screen.getByRole('button', { name: /Générer avec l.IA/ }))
    await screen.findByLabelText('Description proposée')

    fireEvent.click(screen.getByRole('button', { name: 'Fermer' }))

    expect(screen.queryByLabelText('Description proposée')).not.toBeInTheDocument()
    expect(document.getElementById('pf-desc')).toHaveValue('')
  })

  it('une erreur serveur (503 non configuré) affiche un message, sans planter', async () => {
    apiPost.mockRejectedValue({ response: { status: 503, data: { detail: 'Copilote non configuré.' } } })
    renderEdit()
    await screen.findByText(/Éditer/)

    fireEvent.click(screen.getByRole('button', { name: /Générer avec l.IA/ }))

    await waitFor(() => expect(apiPost).toHaveBeenCalled())
    // Aucun dialogue de validation ne s'ouvre sur échec.
    expect(screen.queryByLabelText('Description proposée')).not.toBeInTheDocument()
  })
})
