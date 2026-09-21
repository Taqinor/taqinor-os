import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import authReducer from '../auth/store/authSlice'

/* WIR234 — la CAPA n'avait aucun panneau détail : `capa/<id>/historique`/
   `noter` étaient déjà exposés côté serveur (même `_ChatterMixin` que la
   NCR) sans aucun consommateur côté écran. On vérifie qu'un clic sur une
   ligne CAPA ouvre son panneau détail avec le chatter (jumeau NcrChatter),
   et qu'une note s'y ajoute. Réseau mocké. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
  if (typeof Element.prototype.hasPointerCapture === 'undefined') {
    Element.prototype.hasPointerCapture = () => false
  }
  if (typeof Element.prototype.scrollIntoView === 'undefined') {
    Element.prototype.scrollIntoView = () => {}
  }
})

const CAPA_ROW = {
  id: 55, description: 'Reprendre le joint fenêtre', type_action: 'corrective',
  type_action_display: 'Corrective', statut: 'ouverte', echeance: '2026-09-01',
  efficace: null,
}

const { empty, capaHistorique, capaNoter } = vi.hoisted(() => ({
  empty: () => Promise.resolve({ data: [] }),
  capaHistorique: vi.fn(() => Promise.resolve({ data: [] })),
  capaNoter: vi.fn(() => Promise.resolve({ data: {} })),
}))

vi.mock('../../api/qhseApi', () => ({
  default: {
    nonConformites: { list: empty, historique: empty },
    capa: {
      list: () => Promise.resolve({ data: [CAPA_ROW] }),
      enRetard: empty,
      historique: (...a) => capaHistorique(...a),
      noter: (...a) => capaNoter(...a),
    },
    derogations: { list: empty },
  },
}))

vi.mock('../../ui', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, toast: { success: vi.fn(), error: vi.fn() } }
})

import NonConformites from './NonConformites'

function makeStore() {
  return configureStore({
    reducer: { auth: authReducer },
    preloadedState: {
      auth: {
        user: { id: 1 }, role: 'normal', role_nom: 'Responsable',
        permissions: [], isAuthenticated: true, loading: false,
      },
    },
  })
}

function withProviders(ui) {
  return render(
    <Provider store={makeStore()}>
      <MemoryRouter><ThemeProvider>{ui}</ThemeProvider></MemoryRouter>
    </Provider>,
  )
}

beforeEach(() => { vi.clearAllMocks() })

describe('CapaRegister — panneau détail + chatter (WIR234)', () => {
  it('un clic sur une CAPA ouvre son panneau détail avec le chatter dédié', async () => {
    const user = userEvent.setup()
    withProviders(<NonConformites />)
    await user.click(await screen.findByRole('tab', { name: 'CAPA' }))

    const rows = await screen.findAllByText('Reprendre le joint fenêtre')
    fireEvent.click(rows[0])

    await waitFor(() => expect(capaHistorique).toHaveBeenCalledWith(55))
    expect(await screen.findByText(/Historique CAPA/)).toBeTruthy()
  })

  it('ajoute une note depuis le panneau détail CAPA', async () => {
    const user = userEvent.setup()
    withProviders(<NonConformites />)
    await user.click(await screen.findByRole('tab', { name: 'CAPA' }))

    const rows = await screen.findAllByText('Reprendre le joint fenêtre')
    fireEvent.click(rows[0])
    await waitFor(() => expect(capaHistorique).toHaveBeenCalledWith(55))

    fireEvent.change(screen.getByPlaceholderText('Ajouter une note…'), {
      target: { value: 'Devis de reprise demandé.' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Noter' }))

    await waitFor(() => expect(capaNoter).toHaveBeenCalledWith(
      55, 'Devis de reprise demandé.'))
  })
})
