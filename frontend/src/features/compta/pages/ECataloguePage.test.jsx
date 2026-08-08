import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'

/* PACT39 — Catalogue public à jeton (FG214/XPOS14). Le lien copié pointe vers
   `apps.ventes.public_views.ecatalogue_public` (jamais prix_achat ni marge —
   voir son docstring) : Done= exige que le lien copié n'affiche jamais
   d'information de marge. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
  if (!navigator.clipboard) {
    Object.assign(navigator, { clipboard: { writeText: vi.fn().mockResolvedValue() } })
  }
})

const mocks = vi.hoisted(() => ({ list: vi.fn() }))

vi.mock('../../../api/comptaApi', () => ({
  default: { ecatalogues: { list: mocks.list, update: vi.fn() } },
}))

import ECataloguePage from './ECataloguePage.jsx'

function mount() {
  const store = configureStore({
    reducer: { auth: () => ({ role: 'admin', role_nom: null, permissions: [] }) },
  })
  return render(
    <Provider store={store}>
      <MemoryRouter initialEntries={['/']}>
        <ThemeProvider><ECataloguePage /></ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

describe('ECataloguePage — lien public TTC uniquement (PACT39)', () => {
  it('copie un lien public dérivé du token, jamais un prix d’achat', async () => {
    const clipboardSpy = vi.spyOn(navigator.clipboard, 'writeText')
    mocks.list.mockResolvedValue({
      data: [{ id: 1, titre: 'Catalogue solaire', token: 'abc123xyz', produit_ids: [1, 2],
        actif: true, expire_le: null, date_creation: '2026-01-01' }],
    })
    mount()

    expect(await screen.findByText('Catalogue solaire')).toBeInTheDocument()
    fireEvent.click(await screen.findByRole('button', { name: /Copier le lien public/i }))

    await waitFor(() => expect(clipboardSpy).toHaveBeenCalled())
    expect(clipboardSpy.mock.calls[0][0]).toContain('/api/django/public/ecatalogue/abc123xyz/')
    expect(clipboardSpy.mock.calls[0][0]).not.toMatch(/prix_achat|marge/i)
  })
})
