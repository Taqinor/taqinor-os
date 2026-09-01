import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* WIR120 — section « Avancé » du contrat de maintenance : facturation_active +
   registre d'équipements couverts (au minimum) envoyés à la création. */

const saveContrat = vi.fn(() => Promise.resolve({ data: { id: 1 } }))
vi.mock('../../api/savApi', () => ({
  default: {
    getContrats: vi.fn(() => Promise.resolve({ data: [] })),
    getTickets: vi.fn(() => Promise.resolve({ data: [] })),
    getEquipements: vi.fn(() => Promise.resolve({
      data: [{ id: 9, numero_serie: 'SN-9', produit_nom: 'Onduleur' }],
    })),
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

// WIR231 — l'écran garde l'onglet Rentabilité derrière `prix_achat_voir`
// (useHasPermission → useSelector) : il lui faut donc un store redux.
function makeStore(permissions = []) {
  return configureStore({
    reducer: { auth: (state = { role_nom: 'Responsable', permissions }) => state },
  })
}
function renderPage() {
  return render(
    <Provider store={makeStore()}>
      <MemoryRouter><ThemeProvider><ContratsMaintenance /></ThemeProvider></MemoryRouter>
    </Provider>,
  )
}

describe('WIR120 — contrat de maintenance, section Avancé', () => {
  it('envoie facturation_active + le registre d\'équipements à la création', async () => {
    const user = userEvent.setup()
    renderPage()

    // Client (Radix Select) — premier combobox du formulaire.
    const combos = await screen.findAllByRole('combobox')
    await user.click(combos[0])
    await user.click(await screen.findByRole('option', { name: /ACME/ }))

    // Date de début (natif).
    const dateInputs = document.querySelectorAll('input[type="date"]')
    fireEvent.change(dateInputs[0], { target: { value: '2026-01-01' } })

    // Section Avancé : facturation + un équipement couvert.
    fireEvent.click(screen.getByText(/Avancé —/))
    await user.click(screen.getByRole('checkbox', { name: 'Facturation récurrente active' }))
    await user.click(screen.getByRole('checkbox', { name: 'SN-9 — Onduleur' }))

    fireEvent.click(screen.getByRole('button', { name: /Ajouter/ }))

    await waitFor(() => expect(saveContrat).toHaveBeenCalledWith(
      null, expect.objectContaining({
        client: '3', facturation_active: true, equipements: [9],
      }),
    ))
  })
})
