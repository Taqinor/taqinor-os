import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'

// NTDMO15 — visite guidée par écran : apparaît une fois pour un utilisateur
// récent sur un écran cible, puis ne réapparaît plus après fermeture
// (persistée côté serveur via l'API mockée ci-dessous).
vi.mock('../api/axios', () => ({ default: { get: vi.fn(), post: vi.fn() } }))

import api from '../api/axios'
import ProductTour from './ProductTour'

const RECENT_USER = { id: 1, date_joined: new Date().toISOString() }
const OLD_USER = { id: 2, date_joined: '2020-01-01T00:00:00Z' }

const TOURS = [
  {
    tour_key: 'devis', ecran_cible: '/ventes/devis/nouveau', vu: false,
    etapes: [
      { ordre: 10, selecteur: '', titre: 'Créer un devis', texte: 'Composez votre devis.' },
      { ordre: 20, selecteur: '[data-tour="x"]', titre: 'Ajoutez vos produits', texte: 'Chaque ligne se calcule.' },
    ],
  },
]

function renderTour(user, path = '/ventes/devis/nouveau') {
  const store = configureStore({ reducer: { auth: (s = { user }) => s } })
  return render(
    <Provider store={store}>
      <MemoryRouter initialEntries={[path]}>
        <ProductTour />
      </MemoryRouter>
    </Provider>,
  )
}

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => cleanup())

describe('ProductTour (NTDMO15)', () => {
  it("s'affiche sur l'écran cible pour un utilisateur récent", async () => {
    api.get.mockResolvedValueOnce({ data: TOURS })
    renderTour(RECENT_USER)
    expect(await screen.findByText('Créer un devis')).toBeInTheDocument()
  })

  it('ne s’affiche jamais pour un utilisateur ancien', async () => {
    api.get.mockResolvedValueOnce({ data: TOURS })
    renderTour(OLD_USER)
    await waitFor(() => expect(api.get).toHaveBeenCalled())
    expect(screen.queryByText('Créer un devis')).not.toBeInTheDocument()
  })

  it('ne s’affiche jamais si déjà vu', async () => {
    api.get.mockResolvedValueOnce({
      data: [{ ...TOURS[0], vu: true }],
    })
    renderTour(RECENT_USER)
    await waitFor(() => expect(api.get).toHaveBeenCalled())
    expect(screen.queryByText('Créer un devis')).not.toBeInTheDocument()
  })

  it("Échap ferme le tour et appelle l'API vu/ (ne réapparaît plus)", async () => {
    api.get.mockResolvedValueOnce({ data: TOURS })
    api.post.mockResolvedValueOnce({ data: [{ ...TOURS[0], vu: true }] })
    renderTour(RECENT_USER)
    await screen.findByText('Créer un devis')
    fireEvent.keyDown(window, { key: 'Escape' })
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/onboarding/tours/devis/vu/'))
    expect(screen.queryByText('Créer un devis')).not.toBeInTheDocument()
  })

  it('« Suivant » avance puis « Terminer » ferme et marque vu', async () => {
    api.get.mockResolvedValueOnce({ data: TOURS })
    api.post.mockResolvedValueOnce({ data: [{ ...TOURS[0], vu: true }] })
    renderTour(RECENT_USER)
    await screen.findByText('Créer un devis')
    fireEvent.click(screen.getByRole('button', { name: /Suivant/ }))
    expect(await screen.findByText('Ajoutez vos produits')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Terminer/ }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/onboarding/tours/devis/vu/'))
  })
})
