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
    // WIR62 — onglet Demandes ad-hoc (chargé seulement à l'activation du tab).
    getApprovalRequestTypes: vi.fn(() => Promise.resolve({ data: { results: [] } })),
    getApprovalRequests: vi.fn(() => Promise.resolve({ data: { results: [] } })),
    saveApprovalRequestType: vi.fn(() => Promise.resolve({ data: {} })),
    createApprovalRequest: vi.fn(() => Promise.resolve({ data: {} })),
    approveApprovalRequest: vi.fn(() => Promise.resolve({ data: {} })),
    rejectApprovalRequest: vi.fn(() => Promise.resolve({ data: {} })),
    // WIR261 / ZCTR8 — cycle « complément d'information ».
    demandeInfoApprovalRequest: vi.fn(() => Promise.resolve({ data: {} })),
    resoumettreApprovalRequest: vi.fn(() => Promise.resolve({ data: {} })),
    deleteApprovalRequestType: vi.fn(() => Promise.resolve({ data: {} })),
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

/* ── WIR261 / ZCTR8 — cycle « complément d'information » ────────────────────
   Avant : seules les demandes `pending` étaient chargées, donc une demande
   renvoyée à son émetteur disparaissait de l'écran et n'était plus jamais
   resoumissible. */
describe('WIR261 — demandes ad-hoc : complément d’information', () => {
  const TYPE = { id: 3, nom: 'Note de frais', enabled: true, champs_requis: ['montant'] }
  const EN_ATTENTE = {
    id: 11, request_type: 3, request_type_nom: 'Note de frais',
    demandeur_nom: 'sami', status: 'pending', payload: { montant: '100' },
    min_approbations: 1, approvals_count: 0,
  }
  const INFO = {
    id: 12, request_type: 3, request_type_nom: 'Note de frais',
    demandeur_nom: 'sami', status: 'info_requested',
    decision_note: 'Joindre le justificatif.', payload: { montant: '250' },
    min_approbations: 1, approvals_count: 0,
  }

  function armerMocks() {
    // Ce fichier n'a pas de `beforeEach` global : on remet à zéro les compteurs
    // d'appels des mocks que ces tests observent (jamais l'implémentation —
    // `mockReset` viderait les files `mockResolvedValue`).
    automationApi.demandeInfoApprovalRequest.mockClear()
    automationApi.resoumettreApprovalRequest.mockClear()
    automationApi.deleteApprovalRequestType.mockClear()
    automationApi.getApprovalRequests.mockClear()
    automationApi.getApprovalRequestTypes.mockResolvedValue({ data: { results: [TYPE] } })
    automationApi.getApprovalRequests.mockImplementation((params) => Promise.resolve({
      data: {
        results: params?.status === 'info_requested' ? [INFO] : [EN_ATTENTE],
      },
    }))
  }

  async function ouvrirOnglet() {
    armerMocks()
    renderPage(<ApprobationsPage />)
    await userEvent.click(await screen.findByRole('tab', { name: 'Demandes ad-hoc' }))
  }

  it('charge AUSSI les demandes info_requested et les affiche', async () => {
    await ouvrirOnglet()
    await waitFor(() => expect(automationApi.getApprovalRequests)
      .toHaveBeenCalledWith({ status: 'info_requested' }))
    expect(await screen.findByText('Complément demandé')).toBeInTheDocument()
    expect(screen.getByText(/Joindre le justificatif/)).toBeInTheDocument()
  })

  it('« Demander un complément » poste le motif saisi', async () => {
    vi.spyOn(window, 'prompt').mockReturnValue('Justificatif manquant')
    await ouvrirOnglet()
    await userEvent.click(await screen.findByRole('button', { name: 'Demander un complément' }))
    await waitFor(() => expect(automationApi.demandeInfoApprovalRequest)
      .toHaveBeenCalledWith(11, 'Justificatif manquant'))
  })

  it('un motif vide n’appelle jamais le serveur (motif obligatoire)', async () => {
    vi.spyOn(window, 'prompt').mockReturnValue('   ')
    await ouvrirOnglet()
    await userEvent.click(await screen.findByRole('button', { name: 'Demander un complément' }))
    expect(automationApi.demandeInfoApprovalRequest).not.toHaveBeenCalled()
  })

  it('« Resoumettre » renvoie le payload CORRIGÉ', async () => {
    await ouvrirOnglet()
    await userEvent.click(await screen.findByRole('button', { name: 'Resoumettre' }))
    const champ = await screen.findByDisplayValue('250')
    await userEvent.clear(champ)
    await userEvent.type(champ, '260')
    const boutons = screen.getAllByRole('button', { name: 'Resoumettre' })
    await userEvent.click(boutons[boutons.length - 1])

    await waitFor(() => expect(automationApi.resoumettreApprovalRequest)
      .toHaveBeenCalledWith(12, { montant: '260' }))
  })

  it('supprimer un type appelle deleteApprovalRequestType', async () => {
    await ouvrirOnglet()
    await userEvent.click(
      await screen.findByRole('button', { name: 'Supprimer le type Note de frais' }))
    await waitFor(() => expect(automationApi.deleteApprovalRequestType)
      .toHaveBeenCalledWith(3))
  })
})
