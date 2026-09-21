import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* PACT130 — Done : un écran à DEUX onglets remplace tout besoin de Django
   admin sur les seuils de marge (NTCPQ6) et les paliers d'approbation de
   remise (NTCPQ7/8). Chaque onglet doit donc lire ET écrire. */

const getSeuils = vi.fn()
const createSeuil = vi.fn()
const deleteSeuil = vi.fn()
const getPaliers = vi.fn()
const createPalier = vi.fn()
const updatePalier = vi.fn()
const deletePalier = vi.fn()
const getCategories = vi.fn()

vi.mock('../../api/cpqApi', () => ({
  default: {
    getSeuilsMarge: (...a) => getSeuils(...a),
    createSeuilMarge: (...a) => createSeuil(...a),
    deleteSeuilMarge: (...a) => deleteSeuil(...a),
    getReglesApprobationRemise: (...a) => getPaliers(...a),
    createRegleApprobationRemise: (...a) => createPalier(...a),
    updateRegleApprobationRemise: (...a) => updatePalier(...a),
    deleteRegleApprobationRemise: (...a) => deletePalier(...a),
  },
}))

vi.mock('../../api/stockApi', () => ({
  default: { getCategories: (...a) => getCategories(...a) },
}))

import ParametresCpqPage from './ParametresCpqPage'

function monter() {
  return render(
    <MemoryRouter>
      <ThemeProvider><ParametresCpqPage /></ThemeProvider>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  getSeuils.mockResolvedValue({
    data: { results: [{ id: 1, categorie: 3, categorie_nom: 'Panneaux', marge_min_pct: '18.00' }] },
  })
  createSeuil.mockResolvedValue({ data: { id: 2 } })
  deleteSeuil.mockResolvedValue({ data: {} })
  getPaliers.mockResolvedValue({
    data: {
      results: [{
        id: 9, libelle: 'Remise profonde', remise_min_pct: '10.00',
        remise_max_pct: '20.00', niveau_approbation: 'direction',
        niveau_approbation_display: 'Direction', nombre_approbateurs: 2,
        priorite: 5, actif: true,
      }],
    },
  })
  createPalier.mockResolvedValue({ data: { id: 10 } })
  updatePalier.mockResolvedValue({ data: { id: 9 } })
  deletePalier.mockResolvedValue({ data: {} })
  getCategories.mockResolvedValue({ data: { results: [{ id: 3, nom: 'Panneaux' }] } })
})

describe('ParametresCpqPage (PACT130)', () => {
  it('monte les deux onglets attendus', () => {
    monter()
    expect(screen.getByRole('tab', { name: 'Seuils de marge' })).toBeTruthy()
    expect(screen.getByRole('tab', { name: 'Approbation des remises' })).toBeTruthy()
  })

  it('liste les seuils de marge existants', async () => {
    monter()
    const liste = await screen.findByTestId('cpq-seuil-liste')
    expect(within(liste).getByText('Panneaux')).toBeTruthy()
    expect(within(liste).getByText('18.00 % mini')).toBeTruthy()
  })

  it('crée un seuil de marge pour une catégorie', async () => {
    const user = userEvent.setup()
    monter()
    await waitFor(() => expect(getCategories).toHaveBeenCalled())

    await user.click(screen.getByLabelText('Catégorie'))
    await user.click(await screen.findByRole('option', { name: 'Panneaux' }))
    await user.type(screen.getByLabelText('Marge minimale'), '22,5')
    await user.click(screen.getByTestId('cpq-seuil-creer'))

    await waitFor(() => expect(createSeuil).toHaveBeenCalledWith({
      categorie: 3, marge_min_pct: 22.5,
    }))
  })

  it("n'appelle pas le serveur si la catégorie ou la marge manque", async () => {
    const user = userEvent.setup()
    monter()
    await user.type(screen.getByLabelText('Marge minimale'), '15')
    await user.click(screen.getByTestId('cpq-seuil-creer'))
    expect(createSeuil).not.toHaveBeenCalled()
  })

  it('supprime un seuil de marge', async () => {
    const user = userEvent.setup()
    monter()
    const liste = await screen.findByTestId('cpq-seuil-liste')
    await user.click(within(liste).getByRole('button', { name: /Supprimer/ }))
    await waitFor(() => expect(deleteSeuil).toHaveBeenCalledWith(1))
  })

  it("l'onglet Approbation liste les paliers et en crée un", async () => {
    const user = userEvent.setup()
    monter()
    await user.click(screen.getByRole('tab', { name: 'Approbation des remises' }))
    const liste = await screen.findByTestId('cpq-palier-liste')
    expect(within(liste).getByText('Remise profonde')).toBeTruthy()

    await user.type(screen.getByLabelText('Libellé du palier'), 'Remise moyenne')
    await user.type(screen.getByLabelText('Remise minimale'), '5')
    await user.type(screen.getByLabelText('Remise maximale'), '10')
    await user.click(screen.getByTestId('cpq-palier-creer'))

    await waitFor(() => expect(createPalier).toHaveBeenCalledWith({
      libelle: 'Remise moyenne',
      remise_min_pct: 5,
      remise_max_pct: 10,
      niveau_approbation: 'responsable',
      nombre_approbateurs: 1,
      priorite: 0,
      actif: true,
    }))
  })

  it('bascule un palier actif/inactif', async () => {
    const user = userEvent.setup()
    monter()
    await user.click(screen.getByRole('tab', { name: 'Approbation des remises' }))
    const liste = await screen.findByTestId('cpq-palier-liste')
    await user.click(within(liste).getByRole('button', { name: 'Désactiver' }))
    await waitFor(() => expect(updatePalier).toHaveBeenCalledWith(9, { actif: false }))
  })

  it("remonte le refus serveur sur des bornes incohérentes sans jeter", async () => {
    createPalier.mockRejectedValue({
      response: { data: { remise_max_pct: ['La borne max doit être ≥ la borne min.'] } },
    })
    const user = userEvent.setup()
    monter()
    await user.click(screen.getByRole('tab', { name: 'Approbation des remises' }))
    await screen.findByTestId('cpq-palier-liste')

    await user.type(screen.getByLabelText('Remise minimale'), '20')
    await user.type(screen.getByLabelText('Remise maximale'), '5')
    await user.click(screen.getByTestId('cpq-palier-creer'))

    await waitFor(() => expect(createPalier).toHaveBeenCalled())
    // L'écran reste monté : aucun crash sur un 400 de validation serveur.
    expect(screen.getByTestId('cpq-palier-liste')).toBeTruthy()
  })
})
