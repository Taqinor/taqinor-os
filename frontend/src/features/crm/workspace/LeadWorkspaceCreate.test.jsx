import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'
import crmReducer from '../store/crmSlice'
import crmApi from '../../../api/crmApi'
import LeadWorkspace from './LeadWorkspace'

/* LW12 — mode création : formulaire rapide, défauts VX93, « créer un autre ».
   On neutralise les enfants qui feraient un appel réseau au montage + l'API. */
vi.mock('../../../api/crmApi', () => ({
  default: {
    getAssignableUsers: () => Promise.resolve({ data: [] }),
    getTags: () => Promise.resolve({ data: [] }),
    getMotifsPerte: () => Promise.resolve({ data: [] }),
    getLead: () => Promise.resolve({ data: {} }),
    getLeadDuplicates: () => Promise.resolve({ data: [] }),
    updateLead: () => Promise.resolve({ data: {} }),
    createLead: vi.fn(() => Promise.resolve({ data: { id: 1 } })),
  },
}))
vi.mock('../../../hooks/useDuplicateCheck', () => ({ useDuplicateCheck: () => [] }))
vi.mock('../useCanaux', () => ({ default: () => ({ labels: { walk_in: 'Visite/Walk-in' } }) }))
vi.mock('../../../components/AssigneePicker', () => ({ default: () => <div data-testid="assignee" /> }))
vi.mock('../../../components/CustomFieldsInput', () => ({ default: () => null }))
vi.mock('../../../pages/crm/leads/AppointmentBooker', () => ({ default: () => null }))
vi.mock('../../../pages/crm/leads/LeadDevisPanel', () => ({ default: () => null }))
vi.mock('../../../pages/crm/leads/SigneDialog', () => ({ default: () => null }))
vi.mock('../../../pages/crm/leads/PlanActiviteDialog', () => ({ default: () => null }))
vi.mock('../../../pages/crm/leads/ConvertirClientDialog', () => ({ default: () => null }))

function mockMatchMedia(mobile) {
  window.matchMedia = (query) => ({
    matches: mobile, media: query, onchange: null,
    addEventListener: () => {}, removeEventListener: () => {},
    addListener: () => {}, removeListener: () => {}, dispatchEvent: () => false,
  })
}

beforeEach(() => { mockMatchMedia(false); try { localStorage.clear() } catch { /* noop */ } })
afterEach(() => { cleanup(); vi.clearAllMocks() })

const renderCreate = (props = {}) => {
  const store = configureStore({
    reducer: { crm: crmReducer, auth: (s = { user: { id: 42 } }) => s },
  })
  return render(
    <Provider store={store}>
      <MemoryRouter>
        <LeadWorkspace onClose={props.onClose || vi.fn()} onSaved={vi.fn()} {...props} />
      </MemoryRouter>
    </Provider>,
  )
}
const submitCreateForm = () => fireEvent.submit(document.getElementById('lw-create-form'))
const typeInto = (id, value) => fireEvent.change(document.querySelector(id), { target: { value } })

describe('LW12 — LeadWorkspace création', () => {
  it('ouvre « Nouveau lead » avec le bouton « Créer le lead »', () => {
    renderCreate()
    expect(document.querySelector('[role="dialog"]')).toBeInTheDocument()
    expect(screen.getByText('Nouveau lead')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Créer le lead' })).toBeInTheDocument()
    // Défaut VX93 : owner pré-rempli = utilisateur courant (dans le payload).
    expect(document.querySelector('#lf-nom')).toBeInTheDocument()
  })

  it('« Créer le lead » ferme la fenêtre quand le Switch est OFF', async () => {
    localStorage.setItem('taqinor.leadForm.creerUnAutre', '0')
    const onClose = vi.fn()
    renderCreate({ onClose })
    typeInto('#lf-nom', 'Karim')
    submitCreateForm()
    await waitFor(() => expect(crmApi.createLead).toHaveBeenCalledTimes(1))
    await waitFor(() => expect(onClose).toHaveBeenCalled())
  })

  it('rafale de 2 leads : le 2e garde owner=moi, customData vide, ville mémorisée, focus sur Nom', async () => {
    localStorage.setItem('taqinor.leadForm.creerUnAutre', '1')
    const onClose = vi.fn()
    renderCreate({ onClose })

    typeInto('#lf-nom', 'Karim')
    typeInto('#lf-ville', 'Casablanca')
    submitCreateForm()
    await waitFor(() => expect(crmApi.createLead).toHaveBeenCalledTimes(1))
    const payload1 = crmApi.createLead.mock.calls[0][0]
    expect(payload1.nom).toBe('Karim')
    expect(payload1.owner).toBe('42') // VX93 owner=moi
    expect(payload1.ville).toBe('Casablanca')

    // Switch ON → pas de fermeture, reset complet + refocus #lf-nom.
    expect(onClose).not.toHaveBeenCalled()
    await waitFor(() => expect(document.querySelector('#lf-nom').value).toBe(''))
    await waitFor(() => expect(document.activeElement?.id).toBe('lf-nom'))

    // 2e lead : owner=moi, ville mémorisée, customData vide.
    typeInto('#lf-nom', 'Sara')
    submitCreateForm()
    await waitFor(() => expect(crmApi.createLead).toHaveBeenCalledTimes(2))
    const payload2 = crmApi.createLead.mock.calls[1][0]
    expect(payload2.nom).toBe('Sara')
    expect(payload2.owner).toBe('42')
    expect(payload2.ville).toBe('Casablanca') // mémorisée via rememberVille
    expect(payload2.custom_data).toEqual({}) // parité LW4 (customData purgé)
  })
})
