import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* PACT127 — Done : un ensemble est CRÉÉ avec ses lignes, puis APPLIQUÉ à un
   devis existant depuis l'écran. Les deux moitiés sont vérifiées sur les corps
   réellement envoyés ; la valorisation reste serveur (aucune règle de prix
   n'est rejouée ici). */

const getOffres = vi.fn()
const createOffre = vi.fn()
const deleteOffre = vi.fn()
const appliquer = vi.fn()
const getProduits = vi.fn()
const getDevis = vi.fn()

vi.mock('../../api/cpqApi', () => ({
  default: {
    getOffresGroupees: (...a) => getOffres(...a),
    createOffreGroupee: (...a) => createOffre(...a),
    deleteOffreGroupee: (...a) => deleteOffre(...a),
    appliquerOffreGroupee: (...a) => appliquer(...a),
  },
}))

vi.mock('../../api/stockApi', () => ({
  default: { getProduits: (...a) => getProduits(...a) },
}))

vi.mock('../../api/ventesApi', () => ({
  default: { getDevis: (...a) => getDevis(...a) },
}))

import OffresGroupeesPage from './OffresGroupeesPage'

const PRODUITS = [
  { id: 1, nom: 'Panneau 550 Wc' },
  { id: 2, nom: 'Onduleur 6 kW' },
]

const OFFRES = [
  {
    id: 4,
    nom: 'Pack 6 kWc',
    prix_total: '54000.00',
    actif: true,
    lignes: [
      { id: 40, produit: 1, quantite: '12.00', mode_prix: 'FIXE', valeur: null },
    ],
  },
]

function monter() {
  return render(
    <MemoryRouter>
      <ThemeProvider><OffresGroupeesPage /></ThemeProvider>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  getOffres.mockResolvedValue({ data: { results: OFFRES } })
  createOffre.mockResolvedValue({ data: { id: 5 } })
  deleteOffre.mockResolvedValue({ data: {} })
  appliquer.mockResolvedValue({
    data: {
      detail: 'Offre « Pack 6 kWc » appliquée.',
      lignes_creees: [101, 102],
      sous_total_ht: '54000.00',
    },
  })
  getProduits.mockResolvedValue({ data: { results: PRODUITS } })
  getDevis.mockResolvedValue({ data: { results: [{ id: 77, reference: 'DEV-202608-0003' }] } })
})

describe('OffresGroupeesPage (PACT127)', () => {
  it('liste les offres existantes avec leurs lignes', async () => {
    monter()
    const liste = await screen.findByTestId('cpq-offre-liste')
    expect(within(liste).getByText('Pack 6 kWc')).toBeTruthy()
    await waitFor(() => {
      expect(within(liste).getByText(/Panneau 550 Wc × 12.00/)).toBeTruthy()
    })
  })

  it('crée une offre avec ses lignes (Done PACT127, 1re moitié)', async () => {
    const user = userEvent.setup()
    monter()
    await waitFor(() => expect(getProduits).toHaveBeenCalled())

    await user.type(screen.getByLabelText("Nom de l'offre"), 'Pack pompage')
    await user.type(screen.getByLabelText('Prix total du bundle'), '32000')

    await user.click(screen.getByLabelText('Produit de la ligne 1'))
    await user.click(await screen.findByRole('option', { name: 'Panneau 550 Wc' }))
    const qte1 = screen.getByLabelText('Quantité de la ligne 1')
    await user.clear(qte1)
    await user.type(qte1, '8')

    await user.click(screen.getByTestId('cpq-offre-ajouter-ligne'))
    await user.click(screen.getByLabelText('Produit de la ligne 2'))
    await user.click(await screen.findByRole('option', { name: 'Onduleur 6 kW' }))

    await user.click(screen.getByTestId('cpq-offre-creer'))

    await waitFor(() => expect(createOffre).toHaveBeenCalledWith({
      nom: 'Pack pompage',
      prix_total: 32000,
      actif: true,
      lignes: [
        { produit: 1, quantite: 8, mode_prix: 'FIXE', valeur: null },
        { produit: 2, quantite: 1, mode_prix: 'FIXE', valeur: null },
      ],
    }))
  })

  it("refuse de créer une offre sans aucune ligne produit (aucun appel serveur)", async () => {
    const user = userEvent.setup()
    monter()
    await user.type(screen.getByLabelText("Nom de l'offre"), 'Vide')
    await user.click(screen.getByTestId('cpq-offre-creer'))
    expect(createOffre).not.toHaveBeenCalled()
  })

  it('applique une offre à un devis existant (Done PACT127, 2e moitié)', async () => {
    const user = userEvent.setup()
    monter()
    await screen.findByTestId('cpq-offre-liste')
    await waitFor(() => expect(getDevis).toHaveBeenCalled())

    // Tant qu'aucun devis n'est choisi, l'action reste inerte.
    expect(screen.getByTestId('cpq-offre-appliquer-4')).toBeDisabled()

    await user.click(screen.getByLabelText('Devis cible pour Pack 6 kWc'))
    await user.click(await screen.findByRole('option', { name: 'DEV-202608-0003' }))
    await user.click(screen.getByTestId('cpq-offre-appliquer-4'))

    await waitFor(() => expect(appliquer).toHaveBeenCalledWith(4, '77'))
  })

  it('dégrade proprement quand la liste des offres est indisponible', async () => {
    getOffres.mockRejectedValue({ response: { data: { detail: 'Service indisponible.' } } })
    monter()
    expect(await screen.findByText('Service indisponible.')).toBeTruthy()
  })
})
