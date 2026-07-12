import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import { ConfirmProvider } from '../../providers/ConfirmProvider'

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
  }
})

function renderPage(ui) {
  return render(
    <MemoryRouter>
      <ThemeProvider>
        <ConfirmProvider>{ui}</ConfirmProvider>
      </ThemeProvider>
    </MemoryRouter>,
  )
}

/* XKB1/ZCTR7-9 — La boîte d'approbations centralisée charge TOUTES les
   sources (aucun filtre `source=` par défaut), contrairement à la vue étroite
   de WorkflowsScreen (source=workflow uniquement). */

vi.mock('../../api/reportingApi', () => ({
  default: {
    approbationsEnAttente: vi.fn(() => Promise.resolve({
      data: {
        items: [
          {
            source: 'automation', id: 1, libelle: 'Règle X', demandeur: 'sami',
            priorite: null, anciennete_jours: 2, en_retard: false,
          },
          {
            source: 'installations', id: 7, libelle: 'Réquisition R-007',
            demandeur: null, priorite: 'haute', anciennete_jours: 5, en_retard: true,
          },
        ],
        total: 2,
      },
    })),
    deciderApprobation: vi.fn(() => Promise.resolve({ data: { detail: 'ok' } })),
    deciderApprobationsEnMasse: vi.fn(() => Promise.resolve({
      data: { resultats: [{ source: 'automation', id: 1, ok: true }] },
    })),
  },
}))

// VX103 — Onglet Délégations : suppléant + plage de dates, pur câblage sur
// `automation/approval-delegations/` (aucune décision UI, tout est serveur).
const mockDelegations = [
  {
    id: 5, delegant: 1, delegant_nom: 'reda', suppleant: 2, suppleant_nom: 'meryem',
    date_debut: '2020-01-01T00:00:00Z', date_fin: '2099-01-01T00:00:00Z',
    date_creation: '2020-01-01T00:00:00Z',
  },
]

vi.mock('../../api/automationApi', () => ({
  default: {
    getDelegations: vi.fn(() => Promise.resolve({ data: { results: mockDelegations } })),
    createDelegation: vi.fn(() => Promise.resolve({ data: mockDelegations[0] })),
    deleteDelegation: vi.fn(() => Promise.resolve({ data: {} })),
  },
}))

vi.mock('../../api/axios', () => ({
  default: {
    get: vi.fn(() => Promise.resolve({
      data: { results: [{ id: 1, username: 'reda' }, { id: 2, username: 'meryem' }] },
    })),
  },
}))

import reportingApi from '../../api/reportingApi'
import automationApi from '../../api/automationApi'
import ApprobationsPage from './ApprobationsPage'

describe('ApprobationsPage (XKB1/ZCTR7-9 — boîte d’approbations centralisée)', () => {
  it('charge TOUTES les sources sans filtre par défaut', async () => {
    renderPage(<ApprobationsPage />)

    expect((await screen.findAllByText('Règle X')).length).toBeGreaterThan(0)
    expect(screen.getAllByText('Réquisition R-007').length).toBeGreaterThan(0)

    await waitFor(() => expect(reportingApi.approbationsEnAttente).toHaveBeenCalledWith({}))
  })

  it('affiche le badge « En retard » pour les items au-delà du SLA', async () => {
    renderPage(<ApprobationsPage />)
    expect(await screen.findAllByText('En retard')).not.toHaveLength(0)
  })

  it('approuver une ligne appelle deciderApprobation avec sa source/id', async () => {
    renderPage(<ApprobationsPage />)
    await screen.findAllByText('Règle X')

    const approveButtons = await screen.findAllByTestId('approbation-approve-automation-1')
    approveButtons[0].click()

    await waitFor(() => expect(reportingApi.deciderApprobation).toHaveBeenCalledWith(
      'automation', 1, 'approuver', '',
    ))
  })
})

describe('ApprobationsPage — onglet Délégations (VX103)', () => {
  it('affiche l’onglet Délégations et charge les délégations à l’activation', async () => {
    renderPage(<ApprobationsPage />)

    const tab = await screen.findByRole('tab', { name: 'Délégations' })
    await userEvent.click(tab)

    await waitFor(() => expect(automationApi.getDelegations).toHaveBeenCalled())
    expect((await screen.findAllByText('meryem', { exact: false })).length).toBeGreaterThan(0)
    expect(screen.getAllByText('Active').length).toBeGreaterThan(0)
  })

  it('révoquer une délégation appelle deleteDelegation avec son id', async () => {
    renderPage(<ApprobationsPage />)

    const tab = await screen.findByRole('tab', { name: 'Délégations' })
    await userEvent.click(tab)

    const revokeBtn = await screen.findByTestId('delegation-revoke-5')
    await userEvent.click(revokeBtn)

    // Confirmation Radix maison (jamais window.confirm) : on cherche le bouton
    // de confirmation destructif dans la boîte de dialogue qui s'ouvre.
    const confirmBtn = await screen.findByRole('button', { name: 'Révoquer', exact: true })
    await userEvent.click(confirmBtn)

    await waitFor(() => expect(automationApi.deleteDelegation).toHaveBeenCalledWith(5))
  })
})
