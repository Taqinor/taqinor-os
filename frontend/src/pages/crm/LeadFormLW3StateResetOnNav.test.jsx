import { useState } from 'react'
import { describe, it, expect, vi, afterEach, beforeAll } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import crmReducer from '../../features/crm/store/crmSlice'
import LeadForm from './LeadForm'

/* LW3 — Test de non-transport (DoD) : sélectionner un devis WhatsApp + taper
   une note sur le lead A, naviguer vers B (props `lead` changée SANS
   démonter LeadForm, comme ◀▶/J-K le font), vérifier que waSelected est
   vide et que le composeur de note est vide sur B — aucune fuite d'état
   satellite d'un lead vers l'autre. */

const LEAD_A = {
  id: 101, nom: 'Alaoui', prenom: 'Hassan', stage: 'NEW',
  devis: [{ id: 501, reference: 'DEV-A-1', statut: 'envoye', total_ttc: 12000, date_creation: '2026-07-01' }],
  devis_auto: { pret: true, message: null },
  facture_hiver: 500, facture_ete: null, ete_differente: false,
  custom_data: {}, langue_preferee: 'fr', whatsapp: '0612345678',
}

const LEAD_B = {
  id: 102, nom: 'Bennis', prenom: 'Yassine', stage: 'NEW',
  devis: [], devis_auto: { pret: true, message: null },
  facture_hiver: 0, facture_ete: null, ete_differente: false,
  custom_data: {}, langue_preferee: 'darija', whatsapp: '0698765432',
}

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
    updateLead: (id, data) => Promise.resolve({ data: { ...LEAD_A, ...data } }),
    createLead: () => Promise.resolve({ data: { id: 99, nom: 'Nouveau', devis: [] } }),
    getAssignableUsers: () => Promise.resolve({ data: [] }),
    getTags: () => Promise.resolve({ data: [] }),
    getMotifsPerte: () => Promise.resolve({ data: [] }),
    getLeadDuplicates: () => Promise.resolve({ data: [] }),
    checkDuplicates: () => Promise.resolve({ data: [] }),
    getCanaux: () => Promise.resolve({ data: [] }),
    getLead: (id) => Promise.resolve({ data: id === LEAD_B.id ? LEAD_B : LEAD_A }),
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

// Mime LeadsPage.jsx : possède `lead` en state, le fait avancer via
// `onNavigateLead` SANS démonter LeadForm (même instance) — exactement le
// mécanisme ◀▶/J-K que LW3 corrige.
function Harness({ initialLead, queue }) {
  const [lead, setLead] = useState(initialLead)
  return (
    <LeadForm
      lead={lead}
      leadsQueue={queue}
      onNavigateLead={setLead}
      onClose={vi.fn()}
      onSaved={vi.fn()}
    />
  )
}

function renderHarness() {
  const store = makeStore()
  render(
    <Provider store={store}>
      <Harness initialLead={LEAD_A} queue={[LEAD_A, LEAD_B]} />
    </Provider>,
  )
}

describe('LeadForm LW3 — état satellite ne fuit pas d\'un lead vers l\'autre (◀▶/J-K)', () => {
  it('sélection WhatsApp + note tapées sur A ne survivent pas à la navigation vers B', async () => {
    renderHarness()

    // Sélectionner le devis du lead A pour WhatsApp.
    const waCheckbox = screen.getByLabelText('Sélectionner DEV-A-1 pour WhatsApp')
    fireEvent.click(waCheckbox)
    expect(waCheckbox.checked).toBe(true)

    // Taper une note (pas encore postée).
    const noteInput = screen.getByPlaceholderText('Écrire une note (appel, commentaire…)')
    fireEvent.change(noteInput, { target: { value: 'Rappeler demain' } })
    expect(noteInput.value).toBe('Rappeler demain')

    // Navigation façon Gmail vers le lead suivant (touche J) — `fields` n'a
    // pas changé (isDirty faux) : aucune confirmation, navigation directe.
    fireEvent.keyDown(document, { key: 'j' })

    // Le lead B n'a aucun devis → la case WhatsApp de A a disparu avec lui.
    await waitFor(() =>
      expect(screen.queryByLabelText('Sélectionner DEV-A-1 pour WhatsApp')).not.toBeInTheDocument(),
    )

    // Le composeur de note est reparti à vide sur B — la note de A n'a pas
    // traversé la navigation (elle serait sinon postée sur le MAUVAIS lead).
    const noteInputAfter = screen.getByPlaceholderText('Écrire une note (appel, commentaire…)')
    expect(noteInputAfter.value).toBe('')
  })
})
