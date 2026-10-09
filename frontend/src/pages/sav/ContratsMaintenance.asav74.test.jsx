import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* ASAV74 — D-ASAV-3 (a), tranchée 08/10/2026 : l'écran ne promet plus une
   facturation récurrente qui n'a pas lieu (plus d'écrivain côté serveur,
   ASAV73). Ni case « Facturation récurrente active », ni échéance de
   facturation, ni facturation_active dans le PATCH/POST. */

const saveContrat = vi.fn(() => Promise.resolve({ data: { id: 1 } }))
vi.mock('../../api/savApi', () => ({
  default: {
    getContrats: vi.fn(() => Promise.resolve({ data: [] })),
    getTickets: vi.fn(() => Promise.resolve({ data: [] })),
    getEquipements: vi.fn(() => Promise.resolve({ data: [] })),
    saveContrat: (...a) => saveContrat(...a),
  },
}))
vi.mock('../../api/crmApi', () => ({
  default: { getClients: vi.fn(() => Promise.resolve({ data: [{ id: 3, nom: 'ACME', prenom: '' }] })) },
}))
vi.mock('../../api/installationsApi', () => ({
  default: { getInstallations: vi.fn(() => Promise.resolve({ data: [] })) },
}))

import { Component as ContratsMaintenance } from './ContratsMaintenance.jsx'

afterEach(() => { cleanup(); vi.clearAllMocks() })

const store = configureStore({
  reducer: { auth: (s = { role_nom: 'Responsable', permissions: [] }) => s },
})

describe('ContratsMaintenance ASAV74 — plus de facturation récurrente promise', () => {
  it('aucune case ni échéance de facturation ; le PATCH/POST ne porte pas facturation_active', async () => {
    render(
      <Provider store={store}>
        <MemoryRouter><ThemeProvider><ContratsMaintenance /></ThemeProvider></MemoryRouter>
      </Provider>,
    )
    const combos = await screen.findAllByRole('combobox')
    fireEvent.click(combos[0])
    fireEvent.click(await screen.findByRole('option', { name: /ACME/ }))
    fireEvent.change(document.querySelectorAll('input[type="date"]')[0],
      { target: { value: '2026-01-01' } })
    fireEvent.click(screen.getByText(/Avancé —/))

    expect(screen.queryByRole('checkbox', { name: /Facturation récurrente/ })).toBeNull()
    expect(screen.queryByText(/Facturation récurrente/)).toBeNull()
    expect(screen.queryByText(/prochaine facturation/i)).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: /Ajouter/ }))
    await waitFor(() => expect(saveContrat).toHaveBeenCalled())
    expect(saveContrat.mock.calls[0][1]).not.toHaveProperty('facturation_active')
  })
})
