import { describe, it, expect, vi, afterEach, beforeAll } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* WIR111 — écran de consultation « Retours » : retours matériel + livraison. */

function mockMatchMedia() {
  window.matchMedia = (query) => ({
    matches: false, media: query, onchange: null,
    addEventListener: () => {}, removeEventListener: () => {},
    addListener: () => {}, removeListener: () => {}, dispatchEvent: () => false,
  })
}
beforeAll(() => { if (typeof window.matchMedia !== 'function') mockMatchMedia() })

const { get } = vi.hoisted(() => ({ get: vi.fn() }))
vi.mock('../../api/axios', () => ({ default: { get } }))

import RetoursScreen from './RetoursScreen'

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('RetoursScreen (WIR111)', () => {
  it('charge les retours matériel par défaut', async () => {
    get.mockImplementation((url) => {
      if (url === '/installations/retours-materiel/') {
        return Promise.resolve({ data: [{ id: 1, installation_reference: 'CH-001', statut: 'brouillon', statut_display: 'Brouillon', lignes: [{}] }] })
      }
      return Promise.resolve({ data: [] })
    })
    render(<RetoursScreen />)
    expect(screen.getByRole('tab', { name: 'Retours matériel' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Retours livraison' })).toBeInTheDocument()
    await waitFor(() => expect(get).toHaveBeenCalledWith('/installations/retours-materiel/'))
    expect(await screen.findByText('CH-001')).toBeInTheDocument()
  })

  it('charge les retours livraison en changeant d\'onglet', async () => {
    get.mockImplementation((url) => {
      if (url === '/installations/retours-livraison/') {
        return Promise.resolve({ data: [{ id: 5, livraison_reference: 'LIV-77', motif: 'Casse', statut: 'valide', statut_display: 'Validé', lignes: [] }] })
      }
      return Promise.resolve({ data: [] })
    })
    const user = userEvent.setup()
    render(<RetoursScreen />)
    await user.click(screen.getByRole('tab', { name: 'Retours livraison' }))
    await waitFor(() => expect(get).toHaveBeenCalledWith('/installations/retours-livraison/'))
    expect(await screen.findByText('LIV-77')).toBeInTheDocument()
  })
})
