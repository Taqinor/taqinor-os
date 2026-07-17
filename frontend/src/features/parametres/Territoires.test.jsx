// NTCRM3 — Territoires screen: create + simulate without leaving the screen.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

vi.mock('../../api/axios', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}))
vi.mock('../../ui/confirm', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

import api from '../../api/axios'
import Territoires from './Territoires'

describe('Territoires (NTCRM3)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    api.get.mockResolvedValue({ data: { results: [] } })
  })

  it('loads and displays the empty state when no territoire exists', async () => {
    render(<Territoires />)
    await waitFor(() => expect(api.get).toHaveBeenCalledWith('/territoires/territoires/'))
    expect(await screen.findByText(/Aucun territoire/i)).toBeInTheDocument()
  })

  it('creates a territoire with a simple critère then reloads the list', async () => {
    api.post.mockResolvedValueOnce({ data: { id: 1 } }) // territoire
    api.post.mockResolvedValueOnce({ data: { id: 10 } }) // regle
    api.get.mockResolvedValueOnce({ data: { results: [] } })
    api.get.mockResolvedValueOnce({
      data: {
        results: [{
          id: 1, nom: 'Sud — résidentiel', type_territoire_display: 'Géographique',
          actif: true, membres: [],
        }],
      },
    })

    render(<Territoires />)
    await screen.findByText(/Aucun territoire/i)

    await userEvent.type(screen.getByPlaceholderText(/Nom \(ex/i), 'Sud — résidentiel')
    await userEvent.type(screen.getByPlaceholderText('Ville (critère géo)'), 'Marrakech')
    await userEvent.click(screen.getByRole('button', { name: /Créer le territoire/i }))

    await waitFor(() => expect(api.post).toHaveBeenCalledWith(
      '/territoires/territoires/',
      expect.objectContaining({ nom: 'Sud — résidentiel' }),
    ))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith(
      '/territoires/regles/',
      expect.objectContaining({ territoire: 1 }),
    ))
    expect(await screen.findByText('Sud — résidentiel')).toBeInTheDocument()
  })

  it('simulates an address against a territoire via resoudre/ without navigating away', async () => {
    api.get.mockResolvedValueOnce({
      data: {
        results: [{
          id: 2, nom: 'Nord', type_territoire_display: 'Géographique',
          actif: true, membres: [],
        }],
      },
    })
    api.get.mockResolvedValueOnce({
      data: { matched: true, territoire_nom: 'Nord', assigne_nom: 'com_a' },
    })

    render(<Territoires />)
    const select = await screen.findByTestId('simulation-territoire-select')
    await userEvent.selectOptions(select, '2')
    await userEvent.click(screen.getByRole('button', { name: /^Simuler$/i }))

    await waitFor(() => expect(api.get).toHaveBeenCalledWith(
      '/territoires/territoires/2/resoudre/',
      expect.objectContaining({ params: expect.any(Object) }),
    ))
    expect(await screen.findByTestId('simulation-result')).toHaveTextContent('Nord')
    expect(screen.getByTestId('simulation-result')).toHaveTextContent('com_a')
  })
})
