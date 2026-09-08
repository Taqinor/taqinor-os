import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'
import crmReducer from '../store/crmSlice'
import crmApi from '../../../api/crmApi'
import LeadWorkspace from './LeadWorkspace'

/* RÈGLE FONDATEUR 08/09/2026 — « all the errors should point at the field
   creating this error and even say what is exactly the error so it is easy
   to solve ». Incident déclencheur : « Non enregistré — Réessayer » + un
   toast « Assurez-vous qu'il n'y a pas plus de 3 chiffres avant la virgule »
   SANS jamais dire quel champ (equip_clim_kw). Ce fichier reprend le patron
   de mocks/rendu de LeadWorkspace.test.jsx (même LEAD_A, mêmes neutralisations
   des rails) pour prouver que le chip d'échec d'autosauvegarde NOMME
   désormais le champ fautif, et garde une action « Réessayer » distincte et
   visible. */

vi.mock('../../../hooks/useDuplicateCheck', () => ({ useDuplicateCheck: () => [] }))
vi.mock('../useCanaux', () => ({ default: () => ({ labels: { walk_in: 'Visite/Walk-in' } }) }))
vi.mock('../../../components/AssigneePicker', () => ({ default: () => <div data-testid="assignee" /> }))
vi.mock('../../../components/CustomFieldsInput', () => ({ default: () => null }))
vi.mock('../../../pages/crm/leads/AppointmentBooker', () => ({ default: () => null }))
vi.mock('../../../pages/crm/leads/LeadDevisPanel', () => ({ default: () => null }))
vi.mock('../../../pages/crm/leads/SigneDialog', () => ({ default: () => null }))
vi.mock('../../../pages/crm/leads/PlanActiviteDialog', () => ({ default: () => null }))
vi.mock('../../../pages/crm/leads/ConvertirClientDialog', () => ({ default: () => null }))
vi.mock('./ContextRail', () => ({ default: () => null }))
vi.mock('./IdentityRail', () => ({
  default: () => <div data-testid="identity-rail" />,
}))

const LEAD_A = { id: 1, nom: 'Ali', prenom: 'Ben', stage: 'NEW', is_archived: false }

vi.mock('../../../api/crmApi', () => ({
  default: {
    getAssignableUsers: vi.fn(() => Promise.resolve({ data: [] })),
    getTags: vi.fn(() => Promise.resolve({ data: [] })),
    getMotifsPerte: vi.fn(() => Promise.resolve({ data: [] })),
    getLead: vi.fn(() => Promise.resolve({ data: { id: 1, nom: 'Ali', prenom: 'Ben', stage: 'NEW', is_archived: false } })),
    getLeadDuplicates: vi.fn(() => Promise.resolve({ data: [] })),
    getLeadClientMatch: vi.fn(() => Promise.resolve({ data: [] })),
    getLeadPointsContact: vi.fn(() => Promise.resolve({ data: null })),
    updateLead: vi.fn(() => Promise.resolve({ data: { id: 1 } })),
    createLead: vi.fn(() => Promise.resolve({ data: { id: 1 } })),
    getRelanceEtapesLead: vi.fn(() => Promise.resolve({ data: { count: 0, results: [] } })),
    initialiserRelance: vi.fn(() => Promise.resolve({ data: [{ id: 1 }] })),
  },
}))
vi.mock('../../../api/axios', () => ({
  default: { get: vi.fn(() => Promise.resolve({ data: [] })) },
}))

function mockMatchMedia(mobile) {
  window.matchMedia = (query) => ({
    matches: mobile, media: query, onchange: null,
    addEventListener: () => {}, removeEventListener: () => {},
    addListener: () => {}, removeListener: () => {}, dispatchEvent: () => false,
  })
}

beforeEach(() => { mockMatchMedia(false); try { localStorage.clear() } catch { /* noop */ } })
afterEach(() => { cleanup(); vi.clearAllMocks() })

function makeStore() {
  return configureStore({ reducer: { crm: crmReducer, auth: (s = { user: { id: 42 } }) => s } })
}

function renderEdit(props = {}) {
  return render(
    <Provider store={makeStore()}>
      <MemoryRouter>
        <LeadWorkspace lead={LEAD_A} onClose={vi.fn()} onSaved={vi.fn()} {...props} />
      </MemoryRouter>
    </Provider>,
  )
}

async function settled() {
  await waitFor(() => expect(crmApi.getLead).toHaveBeenCalled())
}

describe('RÈGLE FONDATEUR 08/09/2026 — le chip d’échec d’autosauvegarde NOMME le champ fautif', () => {
  it('un 400 { equip_clim_kw: [...] } fait apparaître « Puissance totale climatisation » dans le chip, avec « Réessayer » toujours visible', async () => {
    crmApi.updateLead.mockRejectedValueOnce({
      response: {
        status: 400,
        data: { equip_clim_kw: ["Assurez-vous qu'il n'y a pas plus de 3 chiffres avant la virgule."] },
      },
    })
    renderEdit()
    await settled()
    fireEvent.change(document.querySelector('#lf-ville'), { target: { value: 'Rabat' } })

    const chip = await waitFor(
      () => screen.getByRole('button', { name: /Puissance totale climatisation/ }),
      { timeout: 3000 },
    )
    expect(chip).toHaveTextContent("Assurez-vous qu'il n'y a pas plus de 3 chiffres avant la virgule.")
    // « Réessayer » reste une action DISTINCTE, jamais absorbée par le clic
    // qui nomme/navigue vers le champ.
    expect(screen.getByRole('button', { name: 'Réessayer' })).toBeInTheDocument()
    // Le brouillon reste intact (même garantie que l'échec réseau générique).
    expect(document.querySelector('#lf-ville').value).toBe('Rabat')
  })

  it('cliquer le chip nommé ne jette pas (jumpToField, cible potentiellement repliée) — Réessayer reste opérant', async () => {
    crmApi.updateLead.mockRejectedValueOnce({
      response: {
        status: 400,
        data: { equip_clim_kw: ['Trop de chiffres.'] },
      },
    })
    renderEdit()
    await settled()
    fireEvent.change(document.querySelector('#lf-ville'), { target: { value: 'Fès' } })
    const chip = await waitFor(
      () => screen.getByRole('button', { name: /Puissance totale climatisation/ }),
      { timeout: 3000 },
    )
    expect(() => fireEvent.click(chip)).not.toThrow()

    // Réessayer relance bien un PATCH (2e appel à updateLead).
    crmApi.updateLead.mockResolvedValueOnce({ data: { id: 1 } })
    fireEvent.click(screen.getByRole('button', { name: 'Réessayer' }))
    await waitFor(() => expect(crmApi.updateLead).toHaveBeenCalledTimes(2))
  })

  it('plusieurs champs en erreur : le message porte la 1re erreur + « (+ N autre(s)) »', async () => {
    crmApi.updateLead.mockRejectedValueOnce({
      response: {
        status: 400,
        data: {
          equip_clim_kw: ["Assurez-vous qu'il n'y a pas plus de 3 chiffres avant la virgule."],
          equip_ve_km_semaine: ['Valeur trop grande.'],
        },
      },
    })
    renderEdit()
    await settled()
    fireEvent.change(document.querySelector('#lf-ville'), { target: { value: 'Agadir' } })
    const chip = await waitFor(
      () => screen.getByRole('button', { name: /Puissance totale climatisation/ }),
      { timeout: 3000 },
    )
    expect(chip).toHaveTextContent('(+ 1 autre)')
  })

  it('un échec SANS champ exploitable (réseau) garde le chip générique historique « Non enregistré — Réessayer »', async () => {
    crmApi.updateLead.mockRejectedValueOnce({ response: { status: 503 } })
    renderEdit()
    await settled()
    fireEvent.change(document.querySelector('#lf-ville'), { target: { value: 'Rabat' } })
    await waitFor(
      () => expect(screen.getByRole('button', { name: /Réessayer/ })).toBeInTheDocument(),
      { timeout: 3000 },
    )
    // Un seul bouton (pas de second « Réessayer » séparé) — comportement
    // historique inchangé pour ce cas, zéro régression.
    expect(screen.getAllByRole('button', { name: /Réessayer/ })).toHaveLength(1)
  })
})
