import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'

vi.mock('../../api/marketingApi', () => ({
  default: {
    unwrapList: (res) => (Array.isArray(res?.data) ? res.data : (res?.data?.results ?? [])),
    versionsFormulaireIntake: {
      list: vi.fn(() => Promise.resolve({ data: [] })),
      create: vi.fn(() => Promise.resolve({ data: { id: 2, version: 2 } })),
      publier: vi.fn(() => Promise.resolve({ data: {} })),
    },
  },
}))

import LandingVersions from './LandingVersions'
import marketingApi from '../../api/marketingApi'

describe('LandingVersions — NTMKT16', () => {
  beforeEach(() => vi.clearAllMocks())

  it('affiche « aucune version publiée » tant que rien n\'est en ligne', async () => {
    marketingApi.versionsFormulaireIntake.list.mockResolvedValueOnce({
      data: [{ id: 1, version: 1, titre: 'Brouillon', publie: false }],
    })
    render(<LandingVersions formulaireId={4} formulaireNom="Pompage" />)
    await waitFor(() => expect(screen.getByTestId('landing-version-en-ligne'))
      .toHaveTextContent('Aucune version publiée'))
    expect(screen.getAllByTestId('landing-version-row')).toHaveLength(1)
  })

  it('crée une nouvelle version sans jamais envoyer le numéro de version', async () => {
    marketingApi.versionsFormulaireIntake.list.mockResolvedValue({ data: [] })
    render(<LandingVersions formulaireId={4} />)
    await waitFor(() => expect(marketingApi.versionsFormulaireIntake.list).toHaveBeenCalled())
    fireEvent.change(screen.getByLabelText('Titre'), { target: { value: 'Nouveau titre' } })
    fireEvent.click(screen.getByRole('button', { name: 'Enregistrer une nouvelle version' }))
    await waitFor(() =>
      expect(marketingApi.versionsFormulaireIntake.create).toHaveBeenCalledWith({
        formulaire: 4, titre: 'Nouveau titre', pitch: '', image_key: '',
      }))
  })

  it('publie une version brouillon et affiche la version en ligne', async () => {
    marketingApi.versionsFormulaireIntake.list
      .mockResolvedValueOnce({ data: [{ id: 7, version: 2, titre: 'V2', publie: false }] })
      .mockResolvedValueOnce({ data: [{ id: 7, version: 2, titre: 'V2', publie: true }] })
    render(<LandingVersions formulaireId={4} />)
    const bouton = await screen.findByRole('button', { name: 'Publier cette version' })
    fireEvent.click(bouton)
    await waitFor(() =>
      expect(marketingApi.versionsFormulaireIntake.publier).toHaveBeenCalledWith(7))
    await waitFor(() => expect(screen.getByTestId('landing-version-en-ligne'))
      .toHaveTextContent('En ligne : v2'))
  })
})
