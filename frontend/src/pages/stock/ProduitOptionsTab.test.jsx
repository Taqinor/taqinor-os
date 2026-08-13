import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import ProduitOptionsTab from './ProduitOptionsTab.jsx'

/* PACT128 — Options de configuration d'un produit. NTCPQ1 (`apps/cpq`)
   livrait déjà `OptionProduit`/`/cpq/options-produit/` SANS AUCUN écran.
   `OptionProduitViewSet` ne filtre pas par produit côté serveur (comme
   `PrixContractuelViewSet`, PACT129) : le filtrage se fait ici côté client
   sur la réponse complète — vérifié en mélangeant deux produits dans le
   mock et en confirmant que seules les options DU produit affiché
   apparaissent. */

const { apiGet, apiPost } = vi.hoisted(() => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(() => Promise.resolve({ data: { id: 99 } })),
}))

vi.mock('../../api/axios', () => ({
  default: { get: (...args) => apiGet(...args), post: (...args) => apiPost(...args) },
}))

beforeEach(() => {
  vi.clearAllMocks()
  apiPost.mockResolvedValue({ data: { id: 99 } })
  apiGet.mockResolvedValue({
    data: [
      { id: 1, produit: 7, groupe_option: 'Onduleur', obligatoire: true },
      { id: 2, produit: 7, groupe_option: 'Batterie', obligatoire: false },
      { id: 3, produit: 42, groupe_option: 'Structure', obligatoire: true },
    ],
  })
})

describe('ProduitOptionsTab (PACT128)', () => {
  it('liste uniquement les groupes d’options DU produit affiché', async () => {
    render(<ProduitOptionsTab produitId={7} />)

    await waitFor(() => expect(screen.getByText('Onduleur')).toBeInTheDocument())
    expect(screen.getByText('Batterie')).toBeInTheDocument()
    // Groupe d'un AUTRE produit (42) : jamais affiché ici.
    expect(screen.queryByText('Structure')).not.toBeInTheDocument()
  })

  it('affiche le caractère obligatoire/optionnel de chaque groupe', async () => {
    render(<ProduitOptionsTab produitId={7} />)

    await waitFor(() => expect(screen.getByText('Onduleur')).toBeInTheDocument())
    expect(screen.getByText('Obligatoire')).toBeInTheDocument()
    expect(screen.getByText('Optionnel')).toBeInTheDocument()
  })

  it('ajoute un nouveau groupe d’options pour ce produit', async () => {
    render(<ProduitOptionsTab produitId={7} />)
    await waitFor(() => expect(screen.getByText('Onduleur')).toBeInTheDocument())

    fireEvent.change(screen.getByLabelText('Groupe d’options'), { target: { value: 'Structure de montage' } })
    fireEvent.click(screen.getByRole('button', { name: /Ajouter/ }))

    await waitFor(() => expect(apiPost).toHaveBeenCalledWith('/cpq/options-produit/', {
      produit: 7, groupe_option: 'Structure de montage', obligatoire: false,
    }))
  })

  it('affiche un état vide quand le produit n’a aucun groupe', async () => {
    apiGet.mockResolvedValue({ data: [] })
    render(<ProduitOptionsTab produitId={7} />)

    await waitFor(() => expect(screen.getByText('Aucun groupe d’options pour ce produit.')).toBeInTheDocument())
  })
})
