import { describe, it, expect, vi, afterEach, beforeAll } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import crmReducer from '../../features/crm/store/crmSlice'
import LeadForm from './LeadForm'

/* VX24 — LeadSummaryBar : bandeau de faits clés en tête de fiche (score,
   montant estimé, prochaine activité, jours depuis dernière modification),
   visible sans avoir à scroller dans les sections détaillées. */

vi.mock('react-router-dom', async (orig) => ({
  ...(await orig()),
  useNavigate: () => vi.fn(),
}))

vi.mock('../../api/axios', () => ({
  default: {
    get: () => Promise.resolve({ data: [] }),
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

function renderLeadForm(lead) {
  const store = makeStore()
  render(
    <Provider store={store}>
      <LeadForm lead={lead} onClose={vi.fn()} onSaved={vi.fn()} />
    </Provider>,
  )
}

const YESTERDAY = new Date(Date.now() - 86400000 * 3).toISOString()

const EDIT_LEAD = {
  id: 42, nom: 'Alaoui', prenom: 'Hassan', stage: 'NEW',
  devis: [], devis_auto: { pret: true, message: null },
  facture_hiver: 500, facture_ete: null, ete_differente: false,
  montant_estime: '125000', score: 82, score_label: 'Chaud',
  date_modification: YESTERDAY,
  next_activity: { summary: 'Rappeler', due_date: '2026-07-15', state: 'upcoming' },
  custom_data: {},
}

describe('LeadForm VX24 — LeadSummaryBar', () => {
  it('affiche le bandeau de faits clés en mode édition', () => {
    renderLeadForm(EDIT_LEAD)
    expect(screen.getByTestId('lead-summary-bar')).toBeInTheDocument()
  })

  it('affiche le montant estimé formaté', () => {
    renderLeadForm(EDIT_LEAD)
    const bar = screen.getByTestId('lead-summary-bar')
    // Le séparateur de milliers fr-FR est une espace fine (U+202F) — on ne
    // teste que les chiffres pour rester robuste au caractère exact.
    expect(bar.textContent.replace(/[^\d]/g, '')).toMatch(/125000/)
  })

  it("affiche la prochaine activité quand elle existe", () => {
    renderLeadForm(EDIT_LEAD)
    const bar = screen.getByTestId('lead-summary-bar')
    expect(bar.textContent).toMatch(/Rappeler/)
  })

  it('affiche les jours depuis la dernière modification', () => {
    renderLeadForm(EDIT_LEAD)
    const bar = screen.getByTestId('lead-summary-bar')
    expect(bar.textContent).toMatch(/Modifié il y a 3 j/)
  })

  it('ne casse pas à la création (aucun lead) — bandeau absent', () => {
    renderLeadForm(null)
    expect(screen.queryByTestId('lead-summary-bar')).not.toBeInTheDocument()
  })
})
