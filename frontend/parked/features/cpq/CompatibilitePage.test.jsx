import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* PACT126 — la grille des règles de compatibilité (NTCPQ1) est éditable et le
   panneau « Tester » poste une sélection de produits en affichant SÉPARÉMENT
   les violations bloquantes et les avertissements — la séparation vient du
   serveur (`bloquantes` / `avertissements`), jamais d'un recalcul local. */

const getRegles = vi.fn()
const createRegle = vi.fn()
const updateRegle = vi.fn()
const deleteRegle = vi.fn()
const valider = vi.fn()
const getProduits = vi.fn()

vi.mock('../../api/cpqApi', () => ({
  default: {
    getContraintesCompatibilite: (...a) => getRegles(...a),
    createContrainteCompatibilite: (...a) => createRegle(...a),
    updateContrainteCompatibilite: (...a) => updateRegle(...a),
    deleteContrainteCompatibilite: (...a) => deleteRegle(...a),
    validerCompatibilite: (...a) => valider(...a),
  },
}))

vi.mock('../../api/stockApi', () => ({
  default: { getProduits: (...a) => getProduits(...a) },
}))

import CompatibilitePage from './CompatibilitePage'

const PRODUITS = [
  { id: 1, nom: 'Onduleur hybride 5 kW' },
  { id: 2, nom: 'Batterie 5 kWh' },
  { id: 3, nom: 'Kit fixation tôle' },
]

const REGLES = [
  {
    id: 11,
    produit_a: 1,
    produit_b: 2,
    type: 'RECOMMANDE',
    message_utilisateur: 'Une batterie complète le hybride.',
    bloquante: false,
  },
]

function monter() {
  return render(
    <MemoryRouter>
      <ThemeProvider><CompatibilitePage /></ThemeProvider>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  getRegles.mockResolvedValue({ data: { results: REGLES } })
  createRegle.mockResolvedValue({ data: { id: 12 } })
  updateRegle.mockResolvedValue({ data: { id: 11 } })
  deleteRegle.mockResolvedValue({ data: {} })
  getProduits.mockResolvedValue({ data: { results: PRODUITS } })
  valider.mockResolvedValue({
    data: {
      valide: false,
      violations: [],
      bloquantes: [{
        type: 'INCOMPATIBLE', produit_a: 1, produit_b: 3,
        message: 'Fixation tôle incompatible.', bloquante: true,
      }],
      avertissements: [{
        type: 'RECOMMANDE', produit_a: 1, produit_b: 2,
        message: 'Une batterie complète le hybride.', bloquante: false,
      }],
    },
  })
})

describe('CompatibilitePage (PACT126)', () => {
  it('affiche la grille des règles avec les noms de produits', async () => {
    monter()
    await waitFor(() => expect(getRegles).toHaveBeenCalled())
    const grille = await screen.findByTestId('cpq-compat-grille')
    await waitFor(() => {
      expect(within(grille).getByText('Onduleur hybride 5 kW')).toBeTruthy()
    })
    expect(within(grille).getByText('Batterie 5 kWh')).toBeTruthy()
  })

  it('crée une règle entre deux produits', async () => {
    const user = userEvent.setup()
    monter()
    await waitFor(() => expect(getProduits).toHaveBeenCalled())

    await user.click(screen.getByLabelText('Produit A'))
    await user.click(await screen.findByRole('option', { name: 'Onduleur hybride 5 kW' }))
    await user.click(screen.getByLabelText('Produit B'))
    await user.click(await screen.findByRole('option', { name: 'Kit fixation tôle' }))
    await user.type(screen.getByLabelText('Message utilisateur'), 'Jamais ensemble.')
    await user.click(screen.getByTestId('cpq-compat-creer'))

    await waitFor(() => expect(createRegle).toHaveBeenCalledWith({
      produit_a: 1,
      produit_b: 3,
      type: 'INCOMPATIBLE',
      message_utilisateur: 'Jamais ensemble.',
    }))
  })

  it('refuse une règle qui relie un produit à lui-même (aucun appel serveur)', async () => {
    const user = userEvent.setup()
    monter()
    await waitFor(() => expect(getProduits).toHaveBeenCalled())

    await user.click(screen.getByLabelText('Produit A'))
    await user.click(await screen.findByRole('option', { name: 'Batterie 5 kWh' }))
    await user.click(screen.getByLabelText('Produit B'))
    await user.click(await screen.findByRole('option', { name: 'Batterie 5 kWh' }))
    await user.click(screen.getByTestId('cpq-compat-creer'))

    expect(createRegle).not.toHaveBeenCalled()
  })

  it('supprime une règle de la grille', async () => {
    const user = userEvent.setup()
    monter()
    const grille = await screen.findByTestId('cpq-compat-grille')
    await user.click(within(grille).getByRole('button', { name: /Supprimer/ }))
    await waitFor(() => expect(deleteRegle).toHaveBeenCalledWith(11))
  })

  it('teste une sélection et sépare bloquantes et avertissements (Done PACT126)', async () => {
    const user = userEvent.setup()
    monter()
    await waitFor(() => expect(getProduits).toHaveBeenCalled())

    const selection = await screen.findByTestId('cpq-compat-selection')
    await user.click(within(selection).getByRole('button', { name: 'Onduleur hybride 5 kW' }))
    await user.click(within(selection).getByRole('button', { name: 'Kit fixation tôle' }))
    await user.click(screen.getByTestId('cpq-compat-tester'))

    await waitFor(() => expect(valider).toHaveBeenCalledWith([1, 3]))

    const bloquantes = await screen.findByTestId('cpq-compat-bloquantes')
    expect(within(bloquantes).getByText('Fixation tôle incompatible.')).toBeTruthy()
    const avertissements = screen.getByTestId('cpq-compat-avertissements')
    expect(
      within(avertissements).getByText('Une batterie complète le hybride.'),
    ).toBeTruthy()
    // La violation bloquante n'apparaît JAMAIS dans le panneau d'avertissements.
    expect(
      within(avertissements).queryByText('Fixation tôle incompatible.'),
    ).toBeNull()
  })

  it('dégrade proprement quand la grille est indisponible', async () => {
    getRegles.mockRejectedValue({ response: { data: { detail: 'Indisponible.' } } })
    monter()
    expect(await screen.findByText('Indisponible.')).toBeTruthy()
  })
})
