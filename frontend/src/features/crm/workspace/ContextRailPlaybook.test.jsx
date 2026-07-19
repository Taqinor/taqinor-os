// WIR14 (porté) — la checklist du playbook (NTCRM13, progression auto-générée
// par apps/crm/receivers.py à chaque changement de stage) est visible depuis
// la fiche lead : onglet « Playbook » du rail contexte. Remplace
// LeadFormWIR14Playbook.test.jsx (l'ancien LeadForm a été supprimé en LW40) —
// mêmes sémantiques : l'affordance de nav existe, le panneau rend la
// progression réelle du bon lead via /crm/leads/<id>/playbook/.
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import ContextRail from './ContextRail'

const PLAYBOOK = [
  { id: 1, tache: 11, tache_libelle: 'Appeler le client', tache_obligatoire: true, fait: false },
  { id: 2, tache: 12, tache_libelle: 'Envoyer la plaquette', tache_obligatoire: false, fait: true, fait_par_nom: 'qa_meriem' },
]

vi.mock('../../../api/axios', () => ({
  default: {
    get: vi.fn((url) => {
      if (String(url).includes('/playbook/')) return Promise.resolve({ data: PLAYBOOK })
      return Promise.resolve({ data: [] })
    }),
    post: vi.fn(() => Promise.resolve({ data: {} })),
  },
}))
vi.mock('../../../api/recordsApi', () => ({
  default: {
    getActivities: vi.fn(() => Promise.resolve({ data: [] })),
    getAttachments: vi.fn(() => Promise.resolve({ data: [] })),
  },
}))
vi.mock('../../../api/crmApi', () => ({
  default: {
    getLeadPointsContact: vi.fn(() => Promise.resolve({ data: null })),
  },
}))
vi.mock('../../../components/ActivitiesPanel', () => ({ default: () => null }))
vi.mock('../../../components/AttachmentsPanel', () => ({ default: () => null }))
vi.mock('./TimelineTab', () => ({ default: () => null }))
vi.mock('./DevisTab', () => ({ default: () => null }))

function makeStore() {
  return configureStore({
    reducer: { auth: (state = { role: 'admin', user: { id: 1 } }) => state },
  })
}

const leadState = () => ({
  leadId: 7,
  mode: 'edit',
  server: { id: 7, devis: [] },
  composer: { note: '', file: null },
  wa: { selected: [], langue: 'fr', preview: null },
})

const renderRail = () => render(
  <Provider store={makeStore()}>
    <ContextRail
      state={leadState()}
      users={[]}
      historique={[]}
      refreshHistorique={() => {}}
      onAction={() => {}}
    />
  </Provider>,
)

describe('WIR14 (porté) — onglet Playbook du rail contexte', () => {
  afterEach(() => cleanup())

  it('affiche un onglet « Playbook » et la checklist avec la progression réelle', async () => {
    renderRail()
    const tab = screen.getByRole('tab', { name: /Playbook/ })
    expect(tab).toBeInTheDocument()
    await userEvent.click(tab)
    expect(await screen.findByText('Appeler le client')).toBeInTheDocument()
    expect(screen.getByText('obligatoire')).toBeInTheDocument()
  })

  it('appelle bien /crm/leads/<id>/playbook/ pour CE lead', async () => {
    renderRail()
    await userEvent.click(screen.getByRole('tab', { name: /Playbook/ }))
    await waitFor(() => expect(screen.getByTestId('playbook-checklist-panel')).toBeInTheDocument())
    const api = (await import('../../../api/axios')).default
    expect(api.get.mock.calls.some(([u]) => String(u).includes('/crm/leads/7/playbook/'))).toBe(true)
  })
})
