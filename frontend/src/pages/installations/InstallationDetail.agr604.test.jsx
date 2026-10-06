import { describe, it, expect, vi, beforeAll, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* AGR604 — régime « Déclaration hors réseau (loi 82-21, art. 3) » + champ
   « Raccordement au réseau » dans la section 82-21 de la fiche chantier.
   Même patron que CHT22 : Radix Select remplacé par un <select> natif. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
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

const updateInstallation = vi.hoisted(() => vi.fn())

vi.mock('../../api/installationsApi', () => ({
  default: {
    getHistorique: () => Promise.resolve({ data: [] }),
    getTypesIntervention: () => Promise.resolve({ data: [] }),
    updateInstallation,
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

function renderDetail(installation) {
  const store = configureStore({
    reducer: { stock: (state = { produits: [{ id: 1, nom: 'Panneau' }] }) => state },
  })
  return render(
    <Provider store={store}>
      <MemoryRouter initialEntries={['/chantiers']}>
        <ThemeProvider>
          <InstallationDetail installation={installation} onClose={() => {}} onSaved={() => {}} />
        </ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('InstallationDetail — AGR604 hors réseau', () => {
  it('offre le régime hors réseau et le raccordement, envoyés au PATCH', async () => {
    updateInstallation.mockResolvedValue({ data: { id: 901 } })
    const user = userEvent.setup()
    renderDetail({ id: 901, reference: 'CH-901', statut: 'signe', annule: false })

    const regime = await screen.findByLabelText('Régime')
    expect(screen.getByRole('option', {
      name: 'Déclaration hors réseau (loi 82-21, art. 3)',
    })).toBeInTheDocument()
    await user.selectOptions(regime, 'declaration_hors_reseau')
    await user.selectOptions(screen.getByLabelText('Raccordement au réseau'), 'hors_reseau')
    await user.click(screen.getByRole('button', { name: 'Mettre à jour' }))

    await waitFor(() => expect(updateInstallation).toHaveBeenCalledTimes(1))
    const [id, data] = updateInstallation.mock.calls[0]
    expect(id).toBe(901)
    expect(data.regime_8221).toBe('declaration_hors_reseau')
    expect(data.raccordement_reseau).toBe('hors_reseau')
  })

  it('enregistrer → rouvrir → enregistrer sans toucher = même PATCH', async () => {
    updateInstallation.mockResolvedValue({ data: { id: 902 } })
    const user = userEvent.setup()
    const chantier = {
      id: 902, reference: 'CH-902', statut: 'signe', annule: false,
      regime_8221: 'declaration_hors_reseau', raccordement_reseau: 'hors_reseau',
    }
    const premier = renderDetail(chantier)
    await screen.findByLabelText('Régime')
    await user.click(screen.getByRole('button', { name: 'Mettre à jour' }))
    await waitFor(() => expect(updateInstallation).toHaveBeenCalledTimes(1))
    premier.unmount()

    renderDetail(chantier)
    await screen.findByLabelText('Régime')
    await user.click(screen.getByRole('button', { name: 'Mettre à jour' }))
    await waitFor(() => expect(updateInstallation).toHaveBeenCalledTimes(2))
    expect(updateInstallation.mock.calls[1]).toEqual(updateInstallation.mock.calls[0])
  })

  it('raccordement non renseigné reste null dans le PATCH', async () => {
    updateInstallation.mockResolvedValue({ data: { id: 903 } })
    const user = userEvent.setup()
    renderDetail({ id: 903, reference: 'CH-903', statut: 'signe', annule: false })
    await screen.findByLabelText('Régime')
    await user.click(screen.getByRole('button', { name: 'Mettre à jour' }))
    await waitFor(() => expect(updateInstallation).toHaveBeenCalled())
    expect(updateInstallation.mock.calls[0][1].raccordement_reseau).toBeNull()
  })
})
