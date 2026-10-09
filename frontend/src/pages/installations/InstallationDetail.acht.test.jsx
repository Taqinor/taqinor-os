import { describe, it, expect, vi, beforeAll, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* ACHT3 — l'écran du chantier masque les gestes que le serveur refuse :
   « Enregistrer la mise en service » seulement depuis « Installé » et hors
   chantier annulé ; sélecteur de statut désactivé sur un chantier annulé. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
  }
})

vi.mock('../../ui', async (importActual) => {
  const actual = await importActual()
  const Passthrough = ({ children }) => <>{children}</>
  return {
    ...actual,
    Select: ({ value, onValueChange, children, disabled }) => {
      const kids = Array.isArray(children) ? children : [children]
      const id = kids.find((c) => c && c.props && c.props.id)?.props?.id
      return (
        <select role="combobox" id={id} value={value ?? ''} disabled={disabled}
                onChange={(e) => onValueChange(e.target.value)}>
          <option value="" />
          {children}
        </select>
      )
    },
    SelectTrigger: Passthrough,
    SelectValue: () => null,
    SelectContent: Passthrough,
    SelectItem: ({ value, children }) => <option value={value}>{children}</option>,
  }
})
vi.mock('./ChantierGateTimeline', () => ({ default: () => null }))
vi.mock('./ChantierChecklist', () => ({ default: () => null }))
vi.mock('../../features/installations/offline/OfflineSyncIndicator', () => ({
  default: () => null,
}))
vi.mock('../../api/installationsApi', () => ({
  default: {
    getHistorique: () => Promise.resolve({ data: [] }),
    getTypesIntervention: () => Promise.resolve({ data: [] }),
  },
}))
vi.mock('../../api/savApi', () => ({
  default: {
    getEquipements: () => Promise.resolve({ data: [] }),
    getTickets: () => Promise.resolve({ data: [] }),
    getContrats: () => Promise.resolve({ data: [] }),
  },
}))
vi.mock('../../api/crmApi', () => ({
  default: { getAssignableUsers: () => Promise.resolve({ data: [] }) },
}))
vi.mock('../../api/ventesApi', () => ({
  default: {
    getDevisById: () => Promise.resolve({ data: { lignes: [] } }),
    getReglementaire: () => Promise.resolve({ data: { results: [] } }),
  },
}))

import InstallationDetail from './InstallationDetail'

const rendre = (row) => render(
  <Provider store={configureStore({ reducer: { stock: (s = { produits: [] }) => s } })}>
    <MemoryRouter initialEntries={['/chantiers']}>
      <ThemeProvider>
        <InstallationDetail installation={row} onClose={() => {}} onSaved={() => {}} />
      </ThemeProvider>
    </MemoryRouter>
  </Provider>,
)

const ouvrirJalons = async (user) => {
  await user.click(await screen.findByRole('tab', { name: /Jalons/ }))
}
const BTN = { name: 'Enregistrer la mise en service' }

afterEach(() => cleanup())

describe('InstallationDetail — ACHT3 gestes refusés masqués', () => {
  it('masque mise en service sur signé', async () => {
    const user = userEvent.setup()
    rendre({ id: 1, reference: 'CH-1', statut: 'signe', annule: false })
    await ouvrirJalons(user)
    expect(screen.queryByRole('button', BTN)).toBeNull()
    expect(screen.getByText(/disponible à partir d’Installé/)).toBeInTheDocument()
  })

  it('désactive le statut sur annulé', async () => {
    const user = userEvent.setup()
    rendre({ id: 2, reference: 'CH-2', statut: 'installe', annule: true })
    expect(await screen.findByLabelText('Statut')).toBeDisabled()
    expect(screen.getByText(/Chantier annulé — réactivez-le/)).toBeInTheDocument()
    await ouvrirJalons(user)
    expect(screen.queryByRole('button', BTN)).toBeNull()
    expect(screen.queryByText('Date de mise en service')).toBeNull()
  })

  it('garde actif sur installé', async () => {
    const user = userEvent.setup()
    rendre({ id: 3, reference: 'CH-3', statut: 'installe', annule: false })
    expect(await screen.findByLabelText('Statut')).toBeEnabled()
    await ouvrirJalons(user)
    expect(screen.getByRole('button', BTN)).toBeInTheDocument()
  })
})
