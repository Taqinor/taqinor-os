import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'

const mocks = vi.hoisted(() => ({ get: vi.fn(), maj: vi.fn() }))

vi.mock('../../api/marketingApi', () => ({
  default: { parametres: { get: mocks.get, maj: mocks.maj } },
}))

import MarketingParametres from './MarketingParametres.jsx'

beforeEach(() => {
  vi.clearAllMocks()
  mocks.get.mockResolvedValue({
    data: {
      id: 1, expediteur_nom: '', expediteur_email: '', expediteur_domaine: '',
      silence_heure_debut: null, silence_heure_fin: null,
      plafond_envois_jour: null, langue_defaut_templates: 'fr',
    },
  })
})

describe('MarketingParametres (NTMKT31)', () => {
  it('charge et affiche les réglages actuels', async () => {
    render(<MarketingParametres />)
    await waitFor(() => expect(mocks.get).toHaveBeenCalledTimes(1))
    expect(await screen.findByTestId('marketing-parametres')).toBeInTheDocument()
  })

  it("modifier le plafond puis enregistrer appelle l'API avec la nouvelle valeur", async () => {
    mocks.maj.mockResolvedValue({
      data: { id: 1, plafond_envois_jour: 500, langue_defaut_templates: 'fr' },
    })
    render(<MarketingParametres />)
    await screen.findByTestId('marketing-parametres')

    fireEvent.change(screen.getByTestId('parametres-plafond'), { target: { value: '500' } })
    fireEvent.click(screen.getByTestId('parametres-enregistrer'))

    await waitFor(() => expect(mocks.maj).toHaveBeenCalledWith(
      expect.objectContaining({ plafond_envois_jour: 500 })))
    expect(await screen.findByText('Réglages enregistrés.')).toBeInTheDocument()
  })
})
