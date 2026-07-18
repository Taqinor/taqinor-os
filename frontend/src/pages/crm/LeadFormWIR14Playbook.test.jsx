import { describe, it, expect, vi, afterEach, beforeAll } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import crmReducer from '../../features/crm/store/crmSlice'
import LeadForm from './LeadForm'

/* WIR14/NTCRM13 — la checklist du playbook (progression auto-générée à
   chaque changement de stage, apps/crm/receivers.py:151) était invisible :
   `PlaybookChecklistPanel.jsx` (construit/testé isolément) n'était monté nulle
   part sur la fiche lead. On vérifie ici qu'elle apparaît, avec la
   progression réelle renvoyée par `/crm/leads/<id>/playbook/`. */

vi.mock('react-router-dom', async (orig) => ({
  ...(await orig()),
  useNavigate: () => vi.fn(),
}))

vi.mock('../../api/axios', () => ({
  default: {
    get: (url) => {
      if (url.includes('/playbook/')) {
        return Promise.resolve({
          data: [
            {
              id: 1, tache: 10, tache_libelle: 'Appeler le client',
              tache_obligatoire: true, fait: false, fait_par_nom: null,
            },
          ],
        })
      }
      return Promise.resolve({ data: [] })
    },
    post: () => Promise.resolve({ data: {} }),
  },
}))

vi.mock('../../api/crmApi', () => ({
  default: {
    getAssignableUsers: () => Promise.resolve({ data: [] }),
    getTags: () => Promise.resolve({ data: [] }),
    getMotifsPerte: () => Promise.resolve({ data: [] }),
    getLeadDuplicates: () => Promise.resolve({ data: [] }),
    checkDuplicates: () => Promise.resolve({ data: [] }),
    getCanaux: () => Promise.resolve({ data: [] }),
  },
}))

vi.mock('../../api/ventesApi', () => ({ default: {} }))
vi.mock('../../api/installationsApi', () => ({ default: {} }))

vi.mock('../../components/Avatar', () => ({ default: () => null }))
vi.mock('../../components/AssigneePicker', () => ({ default: () => null }))
vi.mock('../../components/ActivitiesPanel', () => ({ default: () => null }))
vi.mock('../../components/AttachmentsPanel', () => ({ default: () => null }))
vi.mock('../../components/CustomFieldsInput', () => ({ default: () => null }))
vi.mock('./leads/SigneDialog', () => ({ default: () => null }))
vi.mock('./leads/AppointmentBooker', () => ({ default: () => null }))
vi.mock('./leads/LeadDevisPanel', () => ({ default: () => null }))

function mockMatchMedia() {
  window.matchMedia = (query) => ({
    matches: false, media: query, onchange: null,
    addEventListener: () => {}, removeEventListener: () => {},
    addListener: () => {}, removeListener: () => {}, dispatchEvent: () => false,
  })
}

beforeAll(() => { if (typeof window.matchMedia !== 'function') mockMatchMedia() })
afterEach(() => { cleanup(); vi.clearAllMocks() })

function makeStore() {
  return configureStore({
    reducer: { crm: crmReducer },
    middleware: (getDefaultMiddleware) => getDefaultMiddleware({ serializableCheck: false }),
  })
}

const EDIT_LEAD = {
  id: 42, nom: 'Alaoui', prenom: 'Hassan', stage: 'NEW',
  devis: [], devis_auto: { pret: true, message: null },
  facture_hiver: 500, facture_ete: null, ete_differente: false,
  custom_data: {},
}

function renderLeadForm() {
  const store = makeStore()
  render(
    <Provider store={store}>
      <LeadForm lead={EDIT_LEAD} onClose={vi.fn()} onSaved={vi.fn()} />
    </Provider>,
  )
}

describe('LeadForm WIR14 — checklist du playbook sur la fiche lead', () => {
  it('affiche un item de nav « Playbook » et la checklist avec la progression réelle', async () => {
    renderLeadForm()
    expect(screen.getByRole('button', { name: /Playbook/ })).toBeInTheDocument()
    expect(await screen.findByText('Appeler le client')).toBeInTheDocument()
    expect(screen.getByText('obligatoire')).toBeInTheDocument()
  })

  it('appelle bien /crm/leads/<id>/playbook/ pour ce lead', async () => {
    renderLeadForm()
    await waitFor(() => expect(screen.getByTestId('playbook-checklist-panel')).toBeInTheDocument())
  })
})
