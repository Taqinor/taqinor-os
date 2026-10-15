import { describe, it, expect, vi } from 'vitest'
import { renderLeadWorkspace } from '../../../test/leadWorkspaceHarness'
import { installerHooksLeadWorkspace } from '../../../test/leadWorkspaceMocks'
import { screen, fireEvent, waitFor } from '@testing-library/react'
import ventesApi from '../../../api/ventesApi'
import LeadWorkspace from './LeadWorkspace'

/* PV22 — « Concevoir la toiture (3D) » depuis la fiche lead ne mène plus à un
   écran vide : le geste RÉSOUT d'abord le devis à calepiner. Quatre branches,
   quatre issues visibles pour le commercial. */

vi.mock('../../../pages/crm/leads/LeadDevisPanel', () => ({ default: () => null }))
vi.mock('../../../pages/crm/leads/SigneDialog', () => ({ default: () => null }))

// Même patron que LeadWorkspace.onAction.test.jsx : le rail est intercepté pour
// exposer le contrat `onAction` à un bouton de test.
vi.mock('./IdentityRail', async () => (await import('../../../test/leadWorkspaceMocks'))
  .identityRailMock([[['toiture-3d'], 'toiture-3d']]))

vi.mock('../../../api/crmApi', () => ({
  default: {
    getAssignableUsers: vi.fn(() => Promise.resolve({ data: [] })),
    getTags: vi.fn(() => Promise.resolve({ data: [] })),
    getMotifsPerte: vi.fn(() => Promise.resolve({ data: [] })),
    getLead: vi.fn(() => Promise.resolve({ data: {} })),
    getLeadDuplicates: vi.fn(() => Promise.resolve({ data: [] })),
    getLeadClientMatch: vi.fn(() => Promise.resolve({ data: [] })),
    getLeadPointsContact: vi.fn(() => Promise.resolve({ data: null })),
    // CRX37 — jalons devis fusionnés dans la timeline (enrichissement passif).
    getLeadJalonsDevis: vi.fn(() => Promise.resolve({ data: { results: [] } })),
    updateLead: vi.fn(() => Promise.resolve({ data: {} })),
    createLead: vi.fn(() => Promise.resolve({ data: { id: 1 } })),
  },
}))
vi.mock('../../../api/ventesApi', () => ({
  default: { getDevis: vi.fn(), creerDevisAuto: vi.fn() },
}))

const navigateMock = vi.fn()
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, useNavigate: () => navigateMock }
})

const LEAD = { id: 88, nom: 'Alaoui', prenom: 'Youssef', stage: 'NEW', is_archived: false }

installerHooksLeadWorkspace()

function rendre() {
  return renderLeadWorkspace({ lead: LEAD })
}

const cliquer = () => fireEvent.click(screen.getByText('toiture-3d'))

describe('PV22 — résolution du devis à concevoir', () => {
  it('UN seul devis concevable : on l’ouvre directement, sans rien demander', async () => {
    // QJR636 — le SERVEUR filtre (`?concevable=1`) : un accepté n'arrive
    // jamais ici, aucun tri de statut côté écran.
    ventesApi.getDevis.mockResolvedValue({
      data: [{ id: 412, reference: 'DEV-2026-412', statut: 'brouillon' }],
    })
    rendre()
    cliquer()
    await waitFor(() => expect(ventesApi.getDevis)
      .toHaveBeenCalledWith({ lead: 88, concevable: 1 }))
    await waitFor(() => expect(navigateMock)
      .toHaveBeenCalledWith('/ventes/devis/412/design'))
    expect(ventesApi.creerDevisAuto).not.toHaveBeenCalled()
  })

  it('PLUSIEURS brouillons : le commercial départage, aucun devis n’est deviné', async () => {
    ventesApi.getDevis.mockResolvedValue({
      data: [
        {
          id: 412, reference: 'DEV-2026-412', statut: 'brouillon',
          etude_params: { puissance_kwc: 17.04 }, date_creation: '2026-08-01T10:00:00Z',
        },
        {
          id: 413, reference: 'DEV-2026-413', statut: 'envoye',
          etude_params: { puissance_kwc: 9.9 }, date_creation: '2026-08-02T10:00:00Z',
        },
      ],
    })
    rendre()
    cliquer()

    const liste = await screen.findByTestId('pv22-choix-devis')
    expect(screen.getByText(/Ce lead a plusieurs devis/)).toBeTruthy()
    expect(liste).toHaveTextContent('DEV-2026-412')
    expect(liste).toHaveTextContent('17,04 kWc')
    expect(liste).toHaveTextContent('DEV-2026-413')
    // Rien n'est ouvert tant que le choix n'est pas fait.
    expect(navigateMock).not.toHaveBeenCalled()

    fireEvent.click(screen.getByText('DEV-2026-413'))
    expect(navigateMock).toHaveBeenCalledWith('/ventes/devis/413/design')
  })

  it('AUCUN brouillon : le Copilote en dimensionne un (jamais vide) puis l’ouvre', async () => {
    ventesApi.getDevis.mockResolvedValue({ data: { results: [] } })
    ventesApi.creerDevisAuto.mockResolvedValue({
      data: { id: 900, reference: 'DEV-2026-900', statut: 'brouillon' },
    })
    rendre()
    cliquer()
    await waitFor(() => expect(ventesApi.creerDevisAuto)
      .toHaveBeenCalledWith({ lead: 88 }))
    await waitFor(() => expect(navigateMock)
      .toHaveBeenCalledWith('/ventes/devis/900/design'))
  })

  it('409 : le message SERVEUR est affiché tel quel et renvoie au générateur', async () => {
    ventesApi.getDevis.mockResolvedValue({ data: [] })
    ventesApi.creerDevisAuto.mockRejectedValue({
      response: {
        status: 409,
        data: { detail: "Renseignez la facture d'hiver du lead pour dimensionner le devis." },
      },
    })
    rendre()
    cliquer()

    const message = await screen.findByTestId('pv22-devis-auto-impossible')
    expect(message).toHaveTextContent(
      "Renseignez la facture d'hiver du lead pour dimensionner le devis.")
    expect(navigateMock).not.toHaveBeenCalled()

    fireEvent.click(screen.getByRole('button', { name: 'Ouvrir le générateur' }))
    expect(navigateMock).toHaveBeenCalledWith('/ventes/devis/nouveau?lead=88')
  })
})
