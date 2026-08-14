import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'
import crmReducer from '../store/crmSlice'
import ventesApi from '../../../api/ventesApi'
import LeadWorkspace from './LeadWorkspace'

/* PV22 — « Concevoir la toiture (3D) » depuis la fiche lead ne mène plus à un
   écran vide : le geste RÉSOUT d'abord le devis à calepiner. Quatre branches,
   quatre issues visibles pour le commercial. */

vi.mock('../../../hooks/useDuplicateCheck', () => ({ useDuplicateCheck: () => [] }))
vi.mock('../useCanaux', () => ({ default: () => ({ labels: {} }) }))
vi.mock('../../../components/AssigneePicker', () => ({ default: () => <div data-testid="assignee" /> }))
vi.mock('../../../components/CustomFieldsInput', () => ({ default: () => null }))
vi.mock('../../../pages/crm/leads/AppointmentBooker', () => ({ default: () => null }))
vi.mock('../../../pages/crm/leads/LeadDevisPanel', () => ({ default: () => null }))
vi.mock('../../../pages/crm/leads/SigneDialog', () => ({ default: () => null }))
vi.mock('../../../pages/crm/leads/PlanActiviteDialog', () => ({ default: () => null }))
vi.mock('../../../pages/crm/leads/ConvertirClientDialog', () => ({ default: () => null }))

// Même patron que LeadWorkspace.onAction.test.jsx : le rail est intercepté pour
// exposer le contrat `onAction` à un bouton de test.
vi.mock('./IdentityRail', () => ({
  default: ({ onAction }) => (
    <div data-testid="identity-rail">
      <button type="button" onClick={() => onAction('toiture-3d')}>toiture-3d</button>
    </div>
  ),
}))

vi.mock('../../../api/crmApi', () => ({
  default: {
    getAssignableUsers: vi.fn(() => Promise.resolve({ data: [] })),
    getTags: vi.fn(() => Promise.resolve({ data: [] })),
    getMotifsPerte: vi.fn(() => Promise.resolve({ data: [] })),
    getLead: vi.fn(() => Promise.resolve({ data: {} })),
    getLeadDuplicates: vi.fn(() => Promise.resolve({ data: [] })),
    getLeadClientMatch: vi.fn(() => Promise.resolve({ data: [] })),
    getLeadPointsContact: vi.fn(() => Promise.resolve({ data: null })),
    updateLead: vi.fn(() => Promise.resolve({ data: {} })),
    createLead: vi.fn(() => Promise.resolve({ data: { id: 1 } })),
  },
}))
vi.mock('../../../api/axios', () => ({
  default: { get: vi.fn(() => Promise.resolve({ data: [] })) },
}))
vi.mock('../../../api/ventesApi', () => ({
  default: { getDevis: vi.fn(), creerDevisAuto: vi.fn() },
}))

const navigateMock = vi.fn()
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, useNavigate: () => navigateMock }
})

function mockMatchMedia(mobile) {
  window.matchMedia = (query) => ({
    matches: mobile, media: query, onchange: null,
    addEventListener: () => {}, removeEventListener: () => {},
    addListener: () => {}, removeListener: () => {}, dispatchEvent: () => false,
  })
}

const LEAD = { id: 88, nom: 'Alaoui', prenom: 'Youssef', stage: 'NEW', is_archived: false }

beforeEach(() => { mockMatchMedia(false); try { localStorage.clear() } catch { /* noop */ } })
afterEach(() => { cleanup(); vi.clearAllMocks() })

function rendre() {
  const store = configureStore({
    reducer: { crm: crmReducer, auth: (s = { user: { id: 42 } }) => s },
  })
  return render(
    <Provider store={store}>
      <MemoryRouter>
        <LeadWorkspace lead={LEAD} onClose={vi.fn()} onSaved={vi.fn()} />
      </MemoryRouter>
    </Provider>,
  )
}

const cliquer = () => fireEvent.click(screen.getByText('toiture-3d'))

describe('PV22 — résolution du devis à concevoir', () => {
  it('UN seul brouillon : on l’ouvre directement, sans rien demander', async () => {
    ventesApi.getDevis.mockResolvedValue({
      data: [
        { id: 412, reference: 'DEV-2026-412', statut: 'brouillon' },
        // Un devis ACCEPTÉ du même lead ne doit jamais être choisi : `?statut=`
        // n'existe pas côté serveur, le tri se fait ici.
        { id: 300, reference: 'DEV-2026-300', statut: 'accepte' },
      ],
    })
    rendre()
    cliquer()
    await waitFor(() => expect(ventesApi.getDevis).toHaveBeenCalledWith({ lead: 88 }))
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
          id: 413, reference: 'DEV-2026-413', statut: 'brouillon',
          etude_params: { puissance_kwc: 9.9 }, date_creation: '2026-08-02T10:00:00Z',
        },
      ],
    })
    rendre()
    cliquer()

    const liste = await screen.findByTestId('pv22-choix-devis')
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

  it('422 : le message SERVEUR est affiché tel quel et renvoie au générateur', async () => {
    ventesApi.getDevis.mockResolvedValue({ data: [] })
    ventesApi.creerDevisAuto.mockRejectedValue({
      response: {
        status: 422,
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
