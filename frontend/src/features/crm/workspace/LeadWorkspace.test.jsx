import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'
import crmReducer from '../store/crmSlice'
import crmApi from '../../../api/crmApi'
import LeadWorkspace from './LeadWorkspace'
import SectionContact from './sections/SectionContact'
import { initState } from './draftCore'

/* LW37 — sémantiques MIGRÉES des anciennes suites LeadForm.test.jsx +
   LeadFormVX89ResponsiveDialog.test.jsx sur le NOUVEAU cockpit, PLUS les tests
   d'ADVERSITÉ du moteur d'autosauvegarde (blueprint D2) exigés au DoD LW37.

   L'ancienne fiche n'a plus de bouton « Mettre à jour » : l'édition est
   AUTOSAUVÉE (PATCH partiel débouncé) et la fenêtre reste ouverte (SaveChip
   « ✓ Enregistré »). Les rails (IdentityRail/ContextRail) sont interceptés —
   mêmes idiomes que LeadWorkspace.onAction.test.jsx — pour cibler le SHELL + le
   MOTEUR + les SECTIONS RÉELLES (frappe de champ → PATCH partiel). Le lien
   SIGNED→SigneDialog est prouvé ici au niveau du shell (le lien
   StageControl→onSigne est couvert par StageControl.test.jsx — non dupliqué). */

vi.mock('../../../hooks/useDuplicateCheck', () => ({ useDuplicateCheck: () => [] }))
vi.mock('../useCanaux', () => ({ default: () => ({ labels: { walk_in: 'Visite/Walk-in' } }) }))
vi.mock('../../../components/AssigneePicker', () => ({ default: () => <div data-testid="assignee" /> }))
vi.mock('../../../components/CustomFieldsInput', () => ({ default: () => null }))
vi.mock('../../../pages/crm/leads/AppointmentBooker', () => ({ default: () => null }))
vi.mock('../../../pages/crm/leads/LeadDevisPanel', () => ({ default: () => null }))
// SigneDialog rendu en sonde : prouve l'ouverture par onAction('signe').
vi.mock('../../../pages/crm/leads/SigneDialog', () => ({ default: () => <div data-testid="signe-dialog" /> }))
vi.mock('../../../pages/crm/leads/PlanActiviteDialog', () => ({ default: () => null }))
vi.mock('../../../pages/crm/leads/ConvertirClientDialog', () => ({ default: () => null }))
// ContextRail neutralisé : ses appels réseau (historique/records/marketing) sont
// hors sujet ici — couverts par ContextRail.test.jsx / TimelineTab.test.jsx.
vi.mock('./ContextRail', () => ({ default: () => null }))
// IdentityRail intercepté en harnais onAction (patron onAction.test.jsx) —
// expose un bouton « signe » pour le câblage SIGNED→SigneDialog du shell.
vi.mock('./IdentityRail', () => ({
  default: ({ onAction }) => (
    <div data-testid="identity-rail">
      <button type="button" onClick={() => onAction('signe')}>rail-signe</button>
    </div>
  ),
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

function renderCreate(props = {}) {
  return render(
    <Provider store={makeStore()}>
      <MemoryRouter>
        <LeadWorkspace onClose={vi.fn()} onSaved={vi.fn()} {...props} />
      </MemoryRouter>
    </Provider>,
  )
}

// Attend que le GET complet d'ouverture (LW25 loadFresh) ait bien atterri avant
// toute frappe — évite une course où l'écho serveur écraserait le brouillon.
async function settled() {
  await waitFor(() => expect(crmApi.getLead).toHaveBeenCalled())
}

describe('LW37 — fenêtre : édition autosauvée (migré de LeadForm.test / VX89)', () => {
  it('une édition autosauvée garde la fenêtre OUVERTE et affiche « ✓ Enregistré »', async () => {
    const onClose = vi.fn()
    renderEdit({ onClose })
    await settled()
    fireEvent.change(document.querySelector('#lf-ville'), { target: { value: 'Rabat' } })
    await waitFor(() => expect(screen.getByText('✓ Enregistré')).toBeInTheDocument(), { timeout: 3000 })
    expect(onClose).not.toHaveBeenCalled()
  })

  it('Échap ferme la fenêtre via la garde de sortie (non modifiée → ferme)', async () => {
    const onClose = vi.fn()
    renderEdit({ onClose })
    await settled()
    fireEvent.keyDown(document, { key: 'Escape' })
    await waitFor(() => expect(onClose).toHaveBeenCalled())
  })

  // VX89 — l'auto-focus du Nom en création se teste au niveau de SectionContact
  // (autoFocus={mode==='create'}) SANS l'enveloppe Radix : le FocusScope du
  // Dialog focalise sa 1re cible tabbable au montage, ce qui rend l'assertion de
  // focus initial peu fiable au niveau du shell (raison pour laquelle
  // LeadWorkspaceCreate.test ne teste que le RE-focus après reset de rafale).
  it('en création, le champ Nom (#lf-nom) porte l’auto-focus (SectionContact)', () => {
    render(<SectionContact state={initState({ mode: 'create' })} setField={vi.fn()} errors={{}} mode="create" refData={{}} />)
    expect(document.activeElement?.id).toBe('lf-nom')
  })
})

describe('LW37 — adversité du moteur (blueprint D2)', () => {
  it('autosauvegarde : n’envoie QUE les clés modifiées (PATCH partiel)', async () => {
    renderEdit()
    await settled()
    fireEvent.change(document.querySelector('#lf-ville'), { target: { value: 'Rabat' } })
    await waitFor(
      () => expect(crmApi.updateLead).toHaveBeenCalledWith(1, { ville: 'Rabat' }),
      { timeout: 3000 },
    )
  })

  it('écho canonisé du serveur ré-hydrate le champ (jamais la valeur optimiste)', async () => {
    crmApi.updateLead.mockResolvedValueOnce({
      data: { id: 1, telephone: '212612345678', date_modification: '2026-07-19T10:00:00Z' },
    })
    renderEdit()
    await settled()
    fireEvent.change(document.querySelector('#lf-telephone'), { target: { value: '0612345678' } })
    await waitFor(
      () => expect(document.querySelector('#lf-telephone').value).toBe('212612345678'),
      { timeout: 3000 },
    )
  })

  it('échec réseau : le brouillon reste intact + affordance « Réessayer »', async () => {
    crmApi.updateLead.mockRejectedValueOnce({ response: { status: 503 } })
    renderEdit()
    await settled()
    fireEvent.change(document.querySelector('#lf-ville'), { target: { value: 'Rabat' } })
    await waitFor(
      () => expect(screen.getByRole('button', { name: /Réessayer/ })).toBeInTheDocument(),
      { timeout: 3000 },
    )
    // Le brouillon n'est jamais perdu : le champ garde la valeur tapée.
    expect(document.querySelector('#lf-ville').value).toBe('Rabat')
  })

  it('SIGNED via le rail ouvre SigneDialog, jamais un PATCH d’étape direct', async () => {
    renderEdit()
    await settled()
    fireEvent.click(screen.getByText('rail-signe'))
    expect(screen.getByTestId('signe-dialog')).toBeInTheDocument()
    expect(crmApi.updateLead).not.toHaveBeenCalledWith(1, expect.objectContaining({ stage: 'SIGNED' }))
  })
})

describe('LW37 — rafale J/K + suggestions + icônes (migré VX224/VX249/VX45)', () => {
  it('la touche J navigue vers le lead suivant de la file (gardée par le moteur)', async () => {
    const onNavigateLead = vi.fn()
    const queue = [LEAD_A, { id: 2, nom: 'Sara', prenom: '', stage: 'NEW' }]
    renderEdit({ leadsQueue: queue, onNavigateLead })
    await settled()
    // La touche J est écoutée sur `window` ; un keydown sur `document` y remonte.
    fireEvent.keyDown(document, { key: 'j' })
    await waitFor(() => expect(onNavigateLead).toHaveBeenCalledWith(queue[1]))
  })

  it('VX249 — un champ suggéré (ville VX93) porte le style suggéré, retiré à la 1re frappe', () => {
    localStorage.setItem('vx93.lead.ville', 'Casablanca')
    renderCreate()
    const ville = document.querySelector('#lf-ville')
    expect(ville.value).toBe('Casablanca')
    expect(ville.className).toContain('vx-suggested-field')
    // Deux champs suggérés rendent le même hint (owner VX93 + ville) — on
    // vérifie CELUI de la ville par son id d'accessibilité.
    expect(document.querySelector('#lf-ville-hint')).toHaveTextContent('Suggéré — modifiable')
    fireEvent.change(ville, { target: { value: 'Casablanca-Anfa' } })
    expect(document.querySelector('#lf-ville').className).not.toContain('vx-suggested-field')
  })

  it('VX45 — la navigation des sections rend des icônes lucide (SVG), pas des emojis bruts', () => {
    renderCreate()
    const nav = document.querySelector('.lw-secnav')
    expect(nav.querySelectorAll('svg.lw-secnav-icon').length).toBeGreaterThan(0)
  })
})
