import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import { ConfirmProvider } from '../../providers/ConfirmProvider'

beforeAll(polyfillResizeObserver)

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

// AERR125 — Select natif (Radix ne s'ouvre pas sous jsdom) et sélecteur de
// période réduit à un bouton qui choisit « du 10 au 12 novembre » (début de
// jour, comme le vrai DateRangePicker).
vi.mock('../../ui', async (importActual) => ({
  ...(await import('../../test/selectNatif')).avecSelectNatif(await importActual()),
  DateRangePicker: ({ onChange }) => (
    <button type="button" onClick={() => onChange({
      start: new Date(2026, 10, 10), end: new Date(2026, 10, 12) })}>
      Choisir la période
    </button>
  ),
}))

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
    // WIR62 — onglet Demandes ad-hoc (chargé seulement à l'activation du tab).
    getApprovalRequestTypes: vi.fn(() => Promise.resolve({ data: { results: [] } })),
    getApprovalRequests: vi.fn(() => Promise.resolve({ data: { results: [] } })),
    saveApprovalRequestType: vi.fn(() => Promise.resolve({ data: {} })),
    createApprovalRequest: vi.fn(() => Promise.resolve({ data: {} })),
    approveApprovalRequest: vi.fn(() => Promise.resolve({ data: {} })),
    rejectApprovalRequest: vi.fn(() => Promise.resolve({ data: {} })),
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
import { toast } from '../../ui/confirm'
import { polyfillResizeObserver } from '../../test/selectNatif'

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

describe('ApprobationsPage — AERR59 relecture rejetée', () => {
  it('après une décision, une relecture rejetée garde les demandes restantes + Réessayer', async () => {
    const erreur = vi.spyOn(toast, 'error').mockImplementation(() => {})
    renderPage(<ApprobationsPage />)
    await screen.findAllByText('Règle X')
    reportingApi.approbationsEnAttente.mockRejectedValueOnce(new Error('boom'))
    const boutons = await screen.findAllByTestId('approbation-approve-automation-1')
    boutons[0].click()
    expect(await screen.findByTestId('approbations-pas-a-jour')).toBeInTheDocument()
    expect(screen.getAllByText('Réquisition R-007').length).toBeGreaterThan(0)
    expect(screen.queryByText('Aucune demande en attente')).toBeNull()
    expect(erreur).not.toHaveBeenCalledWith('Chargement des approbations impossible.')
    erreur.mockRestore()
  })
})

describe('ApprobationsPage — AERR125 période de délégation', () => {
  async function creerDelegation() {
    renderPage(<ApprobationsPage />)
    await userEvent.click(await screen.findByRole('tab', { name: 'Délégations' }))
    await screen.findByTestId('delegation-revoke-5')
    fireEvent.change(document.getElementById('delegation-suppleant'), { target: { value: '2' } })
    await userEvent.click(screen.getByRole('button', { name: 'Choisir la période' }))
    await userEvent.click(screen.getByRole('button', { name: 'Déléguer' }))
  }

  it('délégation du 10 au 12 : date_fin en fin de journée locale', async () => {
    automationApi.createDelegation.mockClear()
    await creerDelegation()
    await waitFor(() => expect(automationApi.createDelegation).toHaveBeenCalledTimes(1))
    const { date_debut: debut, date_fin: fin } = automationApi.createDelegation.mock.calls[0][0]
    const d = new Date(debut)
    const f = new Date(fin)
    expect([d.getDate(), d.getHours(), d.getMinutes()]).toEqual([10, 0, 0])
    expect([f.getDate(), f.getHours(), f.getMinutes(), f.getSeconds(), f.getMilliseconds()])
      .toEqual([12, 23, 59, 59, 999])
  })

  it('un 400 sur date_fin est nommé sous la période', async () => {
    automationApi.createDelegation.mockRejectedValueOnce({
      response: { status: 400, data: { date_fin: ['La fin doit suivre le début.'] } } })
    await creerDelegation()
    expect(await screen.findByText('La fin doit suivre le début.')).toBeInTheDocument()
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
