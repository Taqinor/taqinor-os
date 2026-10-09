import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, cleanup } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* ASAV50 — l'écran lit TOUTES les pages (faux serveur paginé à 50 avec
   `next`) : 59 contrats → en-tête « 59 contrats », et les équipements /
   préventifs sont lus au-delà de la page 1. */

const PAGE = 50
const pagine = (total, make) => (params = {}) => {
  const page = params.page || 1
  const debut = (page - 1) * PAGE
  const results = Array.from({ length: Math.max(0, Math.min(PAGE, total - debut)) },
    (_, i) => make(debut + i + 1))
  return Promise.resolve({
    data: { count: total, next: debut + PAGE < total ? `?page=${page + 1}` : null, results },
  })
}

const { getContrats, getEquipements, getTickets } = vi.hoisted(() => ({
  getContrats: vi.fn(), getEquipements: vi.fn(), getTickets: vi.fn(),
}))
vi.mock('../../api/savApi', () => ({
  default: {
    getContrats: (...a) => getContrats(...a),
    getEquipements: (...a) => getEquipements(...a),
    getTickets: (...a) => getTickets(...a),
    getTourneePreventive: vi.fn(),
    planifierTournee: vi.fn(),
    getRentabiliteContrats: vi.fn(),
    saveContratOm: vi.fn(),
  },
}))
vi.mock('../../api/crmApi', async () => (await import('./__tests__/contratsMocks.js')).crmApiMock())
vi.mock('../../api/installationsApi', async () => (await import('./__tests__/contratsMocks.js')).installationsApiMock())
vi.mock('../../api/axios', async () => (await import('./__tests__/contratsMocks.js')).axiosMock())

import { Component as ContratsMaintenance } from './ContratsMaintenance.jsx'

beforeEach(() => {
  vi.clearAllMocks()
  getContrats.mockImplementation(pagine(59, (n) => ({
    id: n, client: n, client_nom: `Client ${n}`, actif: true, periodicite_mois: 12,
  })))
  getEquipements.mockImplementation(pagine(60, (n) => ({ id: n, designation: `Eq ${n}` })))
  getTickets.mockImplementation(pagine(55, (n) => ({ id: n, client: n })))
})
afterEach(() => cleanup())

describe('ContratsMaintenance ASAV50 — toutes les pages', () => {
  it('59 contrats : en-tête « 59 contrats » et les pages 2+ sont demandées', async () => {
    render(
      <Provider store={configureStore({
        reducer: { auth: (s = { role_nom: 'Responsable', permissions: [] }) => s },
      })}>
        <MemoryRouter><ThemeProvider><ContratsMaintenance /></ThemeProvider></MemoryRouter>
      </Provider>,
    )
    expect(await screen.findByText(/59 contrats/)).toBeInTheDocument()
    await waitFor(() => {
      expect(getContrats.mock.calls.some(([p]) => p.page === 2)).toBe(true)
      expect(getEquipements.mock.calls.some(([p]) => p.page === 2)).toBe(true)
      expect(getTickets.mock.calls.some(([p]) => p.page === 2)).toBe(true)
    })
  })
})
