import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { initState } from './draftCore'
import ContextRail from './ContextRail'
import { configureStore } from '@reduxjs/toolkit'
import { Provider } from 'react-redux'

// AttachmentsPanel (onglet Pièces) lit le rôle via useIsAdmin/useSelector —
// un Provider minimal suffit (même motif que LeadForm.test.jsx).
function makeStore() {
  return configureStore({
    reducer: { auth: (state = { role: 'admin', user: { id: 1 } }) => state },
  })
}
function renderWithStore(ui) {
  return render(<Provider store={makeStore()}>{ui}</Provider>)
}

/* LW19 — `ContextRail` : onglets ui/Tabs (Historique · Devis · Activités ·
   Pièces) avec badges de compte, mémorisation de l'onglet actif par session,
   hooks e2e (.act-form/.act-list/a.att-name) préservés dans les onglets
   Activités/Pièces. `userEvent` (pas `fireEvent.click`) pour activer un
   TabsTrigger Radix — même convention que features/flotte/VehiculeDetail.test.jsx.
   On mock uniquement ce que le montage initial (onglet Historique) et les
   panneaux réels (ActivitiesPanel/AttachmentsPanel) déclenchent réellement au
   réseau — aucun mock de DevisTab (aucun effet au montage, tout est déclenché
   au clic). */
vi.mock('../../../api/recordsApi', () => ({
  default: {
    getActivities: vi.fn(() => Promise.resolve({
      data: [{ id: 1, done: false }, { id: 2, done: true }],
    })),
    getActivityTypes: () => Promise.resolve({ data: [] }),
    getAttachments: vi.fn(() => Promise.resolve({ data: [{ id: 9, filename: 'photo.jpg', url: '/x' }] })),
  },
}))
vi.mock('../../../api/crmApi', () => ({
  default: {
    getLeadPointsContact: vi.fn(() => Promise.resolve({ data: { count: 0, timeline: [] } })),
  },
}))

afterEach(() => { cleanup(); vi.clearAllMocks() })
beforeEach(() => { try { sessionStorage.clear() } catch { /* noop */ } })

const leadState = (overrides = {}) => initState({
  lead: {
    id: 7,
    nom: 'Karim',
    devis: [{
      id: 1, reference: 'DEV-2026-001', statut: 'accepte', total_ttc: '15000',
      date_creation: '2026-01-05', option_acceptee: null, chantier: null,
    }],
    devis_auto: { pret: true, manquants: [], message: null },
    ...overrides,
  },
  mode: 'edit',
})

const baseProps = (overrides = {}) => ({
  state: leadState(),
  users: [],
  historique: [],
  refreshHistorique: vi.fn(),
  onAction: vi.fn(),
  ...overrides,
})

describe('LW19 — ContextRail : onglets + badges', () => {
  it('rend 4 onglets, Historique actif par défaut', () => {
    renderWithStore(<ContextRail {...baseProps()} />)
    expect(screen.getByRole('tab', { name: 'Historique' })).toHaveAttribute('data-state', 'active')
    expect(screen.getByRole('tab', { name: /1 devis/ })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Activités' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Pièces' })).toBeInTheDocument()
  })

  it('badge devis = state.server.devis.length (absent quand 0)', () => {
    renderWithStore(<ContextRail {...baseProps({ state: leadState({ devis: [] }) })} />)
    expect(screen.getByRole('tab', { name: 'Devis' })).toBeInTheDocument()
    expect(screen.queryByRole('tab', { name: /Devis \(/ })).toBeNull()
  })

  it('badges Activités/Pièces se peuplent après chargement (recordsApi)', async () => {
    renderWithStore(<ContextRail {...baseProps()} />)
    await waitFor(() => expect(screen.getByRole('tab', { name: /Activités \(1\)/ })).toBeInTheDocument())
    expect(screen.getByRole('tab', { name: /Pièces \(1\)/ })).toBeInTheDocument()
  })

  it('changer d\'onglet (clavier/clic) mémorise le choix par session', async () => {
    const user = userEvent.setup()
    renderWithStore(<ContextRail {...baseProps()} />)
    await user.click(screen.getByRole('tab', { name: /devis/i }))
    expect(screen.getByRole('tab', { name: /devis/i })).toHaveAttribute('data-state', 'active')
    expect(sessionStorage.getItem('taqinor.lw.contextTab')).toBe('devis')
  })

  it('les flèches clavier déplacent le focus entre onglets (Radix, gratuit)', async () => {
    const user = userEvent.setup()
    renderWithStore(<ContextRail {...baseProps()} />)
    screen.getByRole('tab', { name: 'Historique' }).focus()
    await user.keyboard('{ArrowRight}')
    expect(screen.getByRole('tab', { name: /devis/i })).toHaveFocus()
  })

  it('un remontage relit l\'onglet mémorisé en session', () => {
    sessionStorage.setItem('taqinor.lw.contextTab', 'pieces')
    renderWithStore(<ContextRail {...baseProps()} />)
    expect(screen.getByRole('tab', { name: /Pièces/ })).toHaveAttribute('data-state', 'active')
  })

  it('onglet Activités : .act-list et .act-form (hooks e2e) restent atteignables', async () => {
    const user = userEvent.setup()
    renderWithStore(<ContextRail {...baseProps()} />)
    await user.click(screen.getByRole('tab', { name: /Activités/ }))
    await waitFor(() => expect(document.querySelector('.act-list')).toBeInTheDocument())
    await user.click(screen.getByText('＋ Planifier une activité'))
    expect(document.querySelector('.act-form')).toBeInTheDocument()
  })

  it('onglet Pièces : a.att-name (hook e2e) reste présent', async () => {
    const user = userEvent.setup()
    renderWithStore(<ContextRail {...baseProps()} />)
    await user.click(screen.getByRole('tab', { name: /Pièces/ }))
    await waitFor(() => expect(document.querySelector('a.att-name')).toBeInTheDocument())
  })

  it('« Appliquer un plan » dans l\'onglet Activités appelle onAction(\'plan\')', async () => {
    const user = userEvent.setup()
    const onAction = vi.fn()
    renderWithStore(<ContextRail {...baseProps({ onAction })} />)
    await user.click(screen.getByRole('tab', { name: /Activités/ }))
    await user.click(screen.getByText('📋 Appliquer un plan'))
    expect(onAction).toHaveBeenCalledWith('plan')
  })
})
