import { describe, it, expect, vi, beforeAll, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* ADOC73 — deux attestations distinctes (installation / fin de travaux) qui
   transmettent leur type, soumises à pvReady comme PV/BL/dossier, et le motif
   d'un 409 serveur affiché au lieu d'un aperçu vide. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
  }
})

const docs = vi.hoisted(() => ({ attestation: vi.fn() }))
vi.mock('../../api/documentsApi', () => ({ default: docs }))
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

const ouvrirDocuments = async (user) => {
  await user.click(await screen.findByRole('tab', { name: /Documents/ }))
}

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('InstallationDetail — ADOC73 attestations', () => {
  it('fin de travaux transmet type=fin_travaux', async () => {
    docs.attestation.mockReturnValue(new Promise(() => {}))
    const user = userEvent.setup()
    rendre({ id: 7, reference: 'CH-7', statut: 'installe', annule: false })
    await ouvrirDocuments(user)
    await user.click(screen.getByRole('button', { name: 'Attestation de fin de travaux' }))
    await waitFor(() => expect(docs.attestation).toHaveBeenCalledWith(7, 'fin_travaux'))
    await user.click(screen.getByRole('button', { name: 'Fermer' }))
    await user.click(screen.getByRole('button', { name: 'Attestation d’installation' }))
    await waitFor(() => expect(docs.attestation).toHaveBeenLastCalledWith(7, 'installation'))
  })

  it('attestation désactivée tant que pvReady est faux', async () => {
    const user = userEvent.setup()
    rendre({ id: 8, reference: 'CH-8', statut: 'signe', annule: false })
    await ouvrirDocuments(user)
    expect(screen.getByRole('button', { name: 'Attestation de fin de travaux' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Attestation d’installation' })).toBeDisabled()
    expect(docs.attestation).not.toHaveBeenCalled()
  })

  it('un 409 affiche son motif', async () => {
    docs.attestation.mockRejectedValue({
      response: { status: 409, data: { detail: 'Réception non prononcée : attestation refusée.' } },
    })
    const user = userEvent.setup()
    rendre({ id: 9, reference: 'CH-9', statut: 'installe', annule: false })
    await ouvrirDocuments(user)
    await user.click(screen.getByRole('button', { name: 'Attestation de fin de travaux' }))
    expect(await screen.findByText('Réception non prononcée : attestation refusée.'))
      .toBeInTheDocument()
  })
})
