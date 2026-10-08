import { describe, it, expect, vi, beforeAll, afterEach } from 'vitest'
import { render, screen, waitFor, cleanup, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import { ConfirmProvider } from '../../providers/ConfirmProvider'

/* APAR41 — refus unitaire et demande de complément passent par le dialogue
   de motif MAISON (plus de window.prompt) : motif réel transmis (jamais
   « Refusé » codé), confirmation inerte tant que le motif est vide, Annuler
   n'envoie aucune requête. Oracle = dialogue rendu + appels réseau. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
  }
})

vi.mock('../../api/reportingApi', () => ({
  default: {
    approbationsEnAttente: vi.fn(() => Promise.resolve({
      data: {
        items: [{
          source: 'automation', id: 1, libelle: 'Règle X', demandeur: 'sami',
          priorite: null, anciennete_jours: 2, en_retard: false,
        }],
        total: 1,
      },
    })),
    deciderApprobation: vi.fn(() => Promise.resolve({ data: { detail: 'ok' } })),
    deciderApprobationsEnMasse: vi.fn(() => Promise.resolve({ data: { resultats: [] } })),
  },
}))

vi.mock('../../api/automationApi', () => ({
  default: {
    getDelegations: vi.fn(() => Promise.resolve({ data: { results: [] } })),
    getApprovalRequestTypes: vi.fn(() => Promise.resolve({ data: { results: [] } })),
    getApprovalRequests: vi.fn((params) => Promise.resolve({ data: { results:
      params?.status === 'pending'
        ? [{ id: 9, status: 'pending', request_type: 1, request_type_nom: 'Achat',
          payload: {}, requested_by: 2, requested_by_nom: 'sami' }]
        : [] } })),
    approveApprovalRequest: vi.fn(() => Promise.resolve({ data: {} })),
    rejectApprovalRequest: vi.fn(() => Promise.resolve({ data: {} })),
    demandeInfoApprovalRequest: vi.fn(() => Promise.resolve({ data: {} })),
  },
}))

vi.mock('../../api/axios', () => ({
  default: { get: vi.fn(() => Promise.resolve({ data: { results: [] } })) },
}))

import reportingApi from '../../api/reportingApi'
import automationApi from '../../api/automationApi'
import ApprobationsPage from './ApprobationsPage'

function renderPage() {
  const store = configureStore({
    reducer: { auth: (s = { user: { id: 1 }, role: 'admin', permissions: [] }) => s },
  })
  return render(
    <Provider store={store}>
      <MemoryRouter>
        <ThemeProvider>
          <ConfirmProvider><ApprobationsPage /></ConfirmProvider>
        </ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

describe('APAR41 — refus unitaire (file)', () => {
  afterEach(() => { cleanup(); vi.clearAllMocks() })

  it('ouvre le dialogue de motif ; motif réel transmis', async () => {
    const user = userEvent.setup()
    renderPage()
    await user.click((await screen.findAllByTestId('approbation-reject-automation-1'))[0])
    const dialogue = await screen.findByRole('dialog')
    const confirmer = within(dialogue).getByRole('button', { name: 'Confirmer le refus' })
    expect(confirmer).toBeDisabled()
    await user.type(within(dialogue).getByLabelText('Motif du refus'), 'Hors budget')
    await user.click(confirmer)
    await waitFor(() => expect(reportingApi.deciderApprobation).toHaveBeenCalledWith(
      'automation', 1, 'refuser', 'Hors budget'))
  })

  it('Annuler n’envoie aucune requête', async () => {
    const user = userEvent.setup()
    renderPage()
    await user.click((await screen.findAllByTestId('approbation-reject-automation-1'))[0])
    const dialogue = await screen.findByRole('dialog')
    await user.click(within(dialogue).getByRole('button', { name: 'Annuler' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    expect(reportingApi.deciderApprobation).not.toHaveBeenCalled()
  })
})

describe('APAR41 — demandes ad-hoc', () => {
  afterEach(() => { cleanup(); vi.clearAllMocks() })

  it('refus : motif réel, jamais « Refusé »', async () => {
    const user = userEvent.setup()
    renderPage()
    await user.click(await screen.findByRole('tab', { name: 'Demandes ad-hoc' }))
    await user.click(await screen.findByRole('button', { name: /Refuser/ }))
    const dialogue = await screen.findByRole('dialog')
    await user.type(within(dialogue).getByLabelText('Motif du refus'), 'Doublon')
    await user.click(within(dialogue).getByRole('button', { name: 'Confirmer le refus' }))
    await waitFor(() => expect(automationApi.rejectApprovalRequest).toHaveBeenCalledWith(9, 'Doublon'))
  })

  it('complément : motif saisi dans le dialogue', async () => {
    const user = userEvent.setup()
    renderPage()
    await user.click(await screen.findByRole('tab', { name: 'Demandes ad-hoc' }))
    await user.click(await screen.findByTestId('approbation-adhoc-complement-9'))
    const dialogue = await screen.findByRole('dialog')
    await user.type(within(dialogue).getByLabelText('Motif du complément demandé'), 'Joindre le devis')
    await user.click(within(dialogue).getByRole('button', { name: 'Demander le complément' }))
    await waitFor(() => expect(automationApi.demandeInfoApprovalRequest)
      .toHaveBeenCalledWith(9, 'Joindre le devis'))
  })
})
