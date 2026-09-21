import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

/* NTSCM30 — Assistant guidé « Créer une politique de stock » (en lot).
   Critère d'acceptation : sélectionner des produits et valider crée les
   politiques correspondantes en un seul appel. */

const { apiMock } = vi.hoisted(() => ({ apiMock: { get: vi.fn(), post: vi.fn() } }))
vi.mock('../../api/axios', () => ({ default: apiMock }))

import PolitiqueStockWizardPage from './PolitiqueStockWizardPage.jsx'

afterEach(() => {
  cleanup()
  apiMock.get.mockReset()
  apiMock.post.mockReset()
})

function mockListes() {
  apiMock.get.mockImplementation((url) => {
    if (url === '/stock/produits/') {
      return Promise.resolve({
        data: {
          results: [
            { id: 1, nom: 'Onduleur 5kW' },
            { id: 2, nom: 'Panneau 550W' },
          ],
        },
      })
    }
    if (url === '/scm/classification-abc/') {
      return Promise.resolve({
        data: [{ id: 10, produit: 1, classe: 'A' }],
      })
    }
    return Promise.resolve({ data: [] })
  })
}

function mount() {
  return render(
    <MemoryRouter initialEntries={['/scm/politiques-stock/nouveau']}>
      <PolitiqueStockWizardPage />
    </MemoryRouter>,
  )
}

describe('PolitiqueStockWizardPage (NTSCM30)', () => {
  it('sélectionne 2 produits et crée 2 politiques en un appel', async () => {
    mockListes()
    apiMock.post.mockResolvedValue({ data: { nb_politiques: 2 } })
    const user = userEvent.setup()
    mount()

    expect(await screen.findByText('Onduleur 5kW')).toBeInTheDocument()
    expect(screen.getByText('Panneau 550W')).toBeInTheDocument()

    const cases = screen.getAllByRole('checkbox')
    await user.click(cases[0])
    await user.click(cases[1])

    await user.click(screen.getByRole('button', { name: /Suivant/i }))
    expect(await screen.findByText(/Niveau de service/)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /Aperçu/i }))
    expect(await screen.findByText(/2 politique\(s\) de stock seront créées/))
      .toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /Créer 2 politique/i }))

    expect(await screen.findByText(/2 politique\(s\) de stock créée/)).toBeInTheDocument()
    expect(apiMock.post).toHaveBeenCalledWith(
      '/scm/politiques-stock/creer-en-lot/',
      expect.objectContaining({ produit_ids: [1, 2] }),
    )
  })
})
