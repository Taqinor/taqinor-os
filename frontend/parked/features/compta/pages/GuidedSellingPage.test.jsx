import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'

/* PACT38 — Assistant de vente guidée (FG211). Une réponse incohérente doit
   afficher l'alerte renvoyée par `services.evaluer_session_guided_selling`
   (apps/compta/services.py) — jamais un écran silencieusement « complet ». */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  create: vi.fn(),
  evaluer: vi.fn(),
}))

vi.mock('../../../api/comptaApi', () => ({
  default: {
    sessionsGuidedSelling: {
      list: mocks.list, create: mocks.create, update: vi.fn(), evaluer: mocks.evaluer,
    },
  },
}))

import GuidedSellingPage from './GuidedSellingPage.jsx'

function mount() {
  const store = configureStore({
    reducer: { auth: () => ({ role: 'admin', role_nom: null, permissions: [] }) },
  })
  return render(
    <Provider store={store}>
      <MemoryRouter initialEntries={['/']}>
        <ThemeProvider><GuidedSellingPage /></ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

describe('GuidedSellingPage — alerte de cohérence (PACT38)', () => {
  it("affiche l'alerte serveur sur un onduleur sous-dimensionné, jamais « complet »", async () => {
    mocks.list.mockResolvedValue({ data: [] })
    mocks.create.mockResolvedValueOnce({ data: { id: 7 } })
    mocks.evaluer.mockResolvedValueOnce({
      data: {
        id: 7, marche: 'residentiel', reponses: { kwc: 10, onduleur_kw: 3, type_systeme: 'reseau', batterie: false },
        composition: { ratio_onduleur: 0.3, type_systeme: 'reseau', kwc: 10 },
        complet: false,
        alertes: ['Onduleur sous-dimensionné par rapport au champ PV (kWc).'],
      },
    })
    mount()

    fireEvent.click(screen.getAllByRole('button', { name: /Nouvelle session/i })[0])
    fireEvent.change(screen.getByLabelText(/kWc/i), { target: { value: '10' } })
    fireEvent.change(screen.getByLabelText(/onduleur/i), { target: { value: '3' } })
    fireEvent.click(screen.getAllByRole('button', { name: /^Évaluer$/i })[0])

    await waitFor(() => expect(mocks.evaluer).toHaveBeenCalledWith(7))
    expect(await screen.findByText(
      'Onduleur sous-dimensionné par rapport au champ PV (kWc).',
    )).toBeInTheDocument()
    expect(screen.queryByText('Configuration cohérente et complète.')).not.toBeInTheDocument()
  })
})
