import { describe, it, expect, vi, afterEach, beforeAll } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import crmReducer from '../../features/crm/store/crmSlice'
import LeadForm from './LeadForm'

/* VX111 — attacher une pièce jointe à une note du chatter : le bouton
   trombone déclenche l'input fichier natif, le fichier choisi s'affiche en
   aperçu avant envoi, et « Noter » poste en multipart quand un fichier est
   présent. */

vi.mock('react-router-dom', async (orig) => ({
  ...(await orig()),
  useNavigate: () => vi.fn(),
}))

const postSpy = vi.fn(() => Promise.resolve({ data: { id: 1, kind: 'note', body: 'x', created_at: new Date().toISOString() } }))

vi.mock('../../api/axios', () => ({
  default: {
    get: () => Promise.resolve({ data: [] }),
    post: (...args) => postSpy(...args),
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

describe('LeadForm VX111 — attacher une pièce jointe à une note', () => {
  it('affiche un bouton trombone dans le composer de note', () => {
    renderLeadForm()
    expect(screen.getByLabelText('Attacher une pièce jointe à la note')).toBeInTheDocument()
  })

  it('choisir un fichier affiche son nom en aperçu', async () => {
    renderLeadForm()
    const fileInput = document.querySelector('.chatter-note-file-input')
    const file = new File(['x'], 'photo.png', { type: 'image/png' })
    fireEvent.change(fileInput, { target: { files: [file] } })
    await waitFor(() => expect(screen.getByTestId('chatter-note-file-preview')).toBeInTheDocument())
    expect(screen.getByText('photo.png')).toBeInTheDocument()
  })

  it('« Noter » avec un fichier attaché poste en multipart (FormData)', async () => {
    renderLeadForm()
    const fileInput = document.querySelector('.chatter-note-file-input')
    const file = new File(['x'], 'photo.png', { type: 'image/png' })
    fireEvent.change(fileInput, { target: { files: [file] } })
    fireEvent.click(screen.getByRole('button', { name: 'Noter' }))
    await waitFor(() => expect(postSpy).toHaveBeenCalled())
    const [, body, config] = postSpy.mock.calls[0]
    expect(body).toBeInstanceOf(FormData)
    expect(config?.headers?.['Content-Type']).toBe('multipart/form-data')
  })

  it('« Noter » sans fichier reste un POST JSON simple (non-régression)', async () => {
    renderLeadForm()
    fireEvent.change(screen.getByPlaceholderText('Écrire une note (appel, commentaire…)'), {
      target: { value: 'Note texte' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Noter' }))
    await waitFor(() => expect(postSpy).toHaveBeenCalled())
    const [, body] = postSpy.mock.calls[0]
    expect(body).toEqual({ body: 'Note texte' })
  })
})
