import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import authReducer from '../../features/auth/store/authSlice'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* ODY23 — smoke test du cockpit Intelligence : le titre s'affiche, le KPI
   « Actions IA disponibles » se charge (GET /api/django/agent/actions/,
   stubbé), et les cartes OCR/Agent IA se masquent pour un rôle qui n'y a pas
   accès (mêmes gardes que le menu INTELLIGENCE historique). */
vi.mock('../../api/iaApi', () => ({
  default: {
    getAgentActions: vi.fn(() =>
      Promise.resolve({ data: { count: 3, actions: [] } })),
  },
}))

import iaApi from '../../api/iaApi'
import IaCockpit from './IaCockpit.jsx'

function makeStore(role = 'admin') {
  return configureStore({
    reducer: { auth: authReducer },
    preloadedState: {
      auth: {
        user: { id: 1 }, role, role_nom: 'Directeur',
        permissions: [], isAuthenticated: true, loading: false,
      },
    },
  })
}

function renderWith(ui, role) {
  return render(
    <Provider store={makeStore(role)}>
      <MemoryRouter>
        <ThemeProvider>{ui}</ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

beforeEach(() => { vi.clearAllMocks() })

describe('IaCockpit', () => {
  it('affiche le titre et le KPI Actions IA (admin voit les 3 cartes)', async () => {
    renderWith(<IaCockpit />, 'admin')
    expect(screen.getByText('Intelligence')).toBeInTheDocument()
    expect(screen.getByText('Traitement OCR')).toBeInTheDocument()
    expect(screen.getByText('Agent IA conversationnel')).toBeInTheDocument()
    await waitFor(() => expect(screen.getByText('3')).toBeInTheDocument())
    expect(iaApi.getAgentActions).toHaveBeenCalledTimes(1)
  })

  it('masque OCR et Agent IA pour un rôle normal (garde historique du menu)', async () => {
    renderWith(<IaCockpit />, 'normal')
    expect(screen.getByText('Actions IA disponibles')).toBeInTheDocument()
    expect(screen.queryByText('Traitement OCR')).not.toBeInTheDocument()
    expect(screen.queryByText('Agent IA conversationnel')).not.toBeInTheDocument()
    await waitFor(() => expect(screen.getByText('3')).toBeInTheDocument())
  })
})
