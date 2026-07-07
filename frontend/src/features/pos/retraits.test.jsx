import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* XPOS15 — smoke de la file click-and-collect (API mockée). */

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
    getRetraits: () => Promise.resolve({
      data: { results: [
        { id: 1, reference: 'RET-0001', statut: 'a_preparer', client_nom: 'Client A', lignes: [{ id: 1 }] },
        { id: 2, reference: 'RET-0002', statut: 'pret', client_nom: 'Client B', lignes: [] },
      ] },
    }),
    marquerPret: () => Promise.resolve({ data: {} }),
    remettreRetrait: () => Promise.resolve({ data: {} }),
  },
}))

import RetraitsScreen from './RetraitsScreen'

function withProviders(ui) {
  return render(
    <MemoryRouter>
      <ThemeProvider>{ui}</ThemeProvider>
    </MemoryRouter>,
  )
}

describe('rendu smoke de RetraitsScreen', () => {
  it('affiche la file et les actions par statut', async () => {
    withProviders(<RetraitsScreen />)
    expect(screen.getByRole('heading', { name: /Retraits en magasin/ })).toBeInTheDocument()
    await waitFor(() => expect(screen.getByTestId('retraits-liste')).toBeInTheDocument())
    expect(screen.getByText('RET-0001')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Marquer prêt/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Remettre/ })).toBeInTheDocument()
  })
})
