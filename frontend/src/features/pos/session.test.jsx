import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* XPOS4 — smoke de l'écran Sessions de caisse (API mockée, hors réseau). */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

vi.mock('../../api/posApi', () => ({
  default: {
    getSessions: () => Promise.resolve({
      data: { results: [
        { id: 1, caisse_comptable: 7, statut: 'ouverte', fond_ouverture: '200' },
      ] },
    }),
    ouvrirSession: () => Promise.resolve({ data: { id: 2 } }),
    cloturerSession: () => Promise.resolve({ data: {} }),
    rapportZ: () => Promise.resolve({ data: { nb_ventes: 0, total: '0', par_mode: {} } }),
  },
}))

vi.mock('../../api/axios', () => ({
  default: {
    get: () => Promise.resolve({ data: { results: [{ id: 7, libelle: 'Caisse magasin' }] } }),
    defaults: { baseURL: '' },
  },
}))

import SessionScreen from './SessionScreen'

function withProviders(ui) {
  return render(
    <MemoryRouter>
      <ThemeProvider>{ui}</ThemeProvider>
    </MemoryRouter>,
  )
}

describe('rendu smoke de SessionScreen', () => {
  it('affiche le titre et la session ouverte chargée', async () => {
    withProviders(<SessionScreen />)
    expect(screen.getByRole('heading', { name: /Sessions de caisse/ })).toBeInTheDocument()
    await waitFor(() => expect(screen.getByTestId('sessions-liste')).toBeInTheDocument())
    expect(screen.getByText('Caisse magasin')).toBeInTheDocument()
    expect(screen.getByText('Ouverte')).toBeInTheDocument()
  })
})
