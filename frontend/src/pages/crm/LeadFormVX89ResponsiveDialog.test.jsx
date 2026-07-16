import { describe, it, expect, vi, afterEach, beforeAll } from 'vitest'
import { render, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import crmReducer from '../../features/crm/store/crmSlice'
import LeadForm from './LeadForm'

/* VX89 — LeadForm : Escape ferme la fiche (onClose), et l'ouverture focus le
   champ Nom — le modal n°1 de l'ERP (20-40 ouvertures/jour/commercial) était
   jusqu'ici le SEUL formulaire à ne répondre ni à l'un ni à l'autre. */

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

function renderLeadForm(props = {}) {
  const store = makeStore()
  const onClose = props.onClose ?? vi.fn()
  render(
    <Provider store={store}>
      <LeadForm onClose={onClose} onSaved={vi.fn()} {...props} />
    </Provider>,
  )
  return { onClose }
}

describe('LeadForm VX89 — ResponsiveDialog (Escape + autofocus)', () => {
  it('rend un [role="dialog"] (shell ResponsiveDialog, plus de div.modal-overlay brute)', () => {
    renderLeadForm()
    expect(document.querySelector('[role="dialog"]')).toBeInTheDocument()
  })

  it('Escape appelle onClose', async () => {
    const { onClose } = renderLeadForm()
    fireEvent.keyDown(document.activeElement || document.body, { key: 'Escape' })
    await waitFor(() => expect(onClose).toHaveBeenCalled())
  })

  it('le champ Nom porte autoFocus (reçoit le focus à l\'ouverture)', () => {
    renderLeadForm()
    const nomInput = document.getElementById('lf-nom')
    expect(nomInput).toBeInTheDocument()
    // jsdom applique le comportement autoFocus au montage : le champ devient
    // l'élément actif — c'est le comportement réel qu'autoFocus produit
    // (plus fiable qu'une assertion sur l'attribut HTML sérialisé).
    expect(document.activeElement).toBe(nomInput)
  })
})
