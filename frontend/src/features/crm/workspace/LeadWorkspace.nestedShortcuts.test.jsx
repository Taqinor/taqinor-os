import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { createPortal } from 'react-dom'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'
import crmReducer from '../store/crmSlice'
import crmApi from '../../../api/crmApi'
import LeadWorkspace from './LeadWorkspace'
import { toastWithUndo } from '../../../lib/toast'

/* INCIDENT 02/10/2026 — lead « ouissam merbahi » archivé sans le vouloir.
   Meryem modifiait le devis du lead dans le panneau devis ouvert DEPUIS la
   fiche (LeadDevisPanel, une Sheet posée par-dessus la fiche). La fiche
   restait montée, son écouteur clavier `window` aussi : une touche « a »
   tapée dans le panneau devis hors d'un champ texte (après un clic sur un
   bouton, une case, un sélecteur…) archivait le lead sans confirmation et
   refermait tout. Les touches 1-4 (étape) avaient le même défaut.
   Garde : une touche tapée dans une boîte de dialogue posée PAR-DESSUS la
   fiche n'atteint jamais les raccourcis de la fiche ; et l'archivage n'a
   plus de raccourci à une touche. */
vi.mock('../../../hooks/useDuplicateCheck', () => ({ useDuplicateCheck: () => [] }))
vi.mock('../useCanaux', () => ({ default: () => ({ labels: { walk_in: 'Visite/Walk-in' } }) }))
vi.mock('../../../components/AssigneePicker', () => ({ default: () => <div data-testid="assignee" /> }))
vi.mock('../../../components/CustomFieldsInput', () => ({ default: () => null }))
vi.mock('../../../pages/crm/leads/AppointmentBooker', () => ({ default: () => null }))
// Le panneau devis réel est une Sheet Radix rendue en PORTAIL sur <body>, hors
// de la boîte de dialogue de la fiche — on reproduit exactement cette forme.
vi.mock('../../../pages/crm/leads/LeadDevisPanel', () => ({
  default: () => createPortal(
    <div role="dialog" data-state="open" data-testid="devis-panel">
      <button type="button" data-testid="devis-btn">Option 2</button>
    </div>,
    document.body,
  ),
}))
vi.mock('../../../pages/crm/leads/SigneDialog', () => ({ default: () => null }))
vi.mock('../../../pages/crm/leads/PlanActiviteDialog', () => ({ default: () => null }))
vi.mock('../../../pages/crm/leads/ConvertirClientDialog', () => ({ default: () => null }))

vi.mock('../../../api/crmApi', () => ({
  default: {
    getAssignableUsers: vi.fn(() => Promise.resolve({ data: [] })),
    getTags: vi.fn(() => Promise.resolve({ data: [] })),
    getMotifsPerte: vi.fn(() => Promise.resolve({ data: [] })),
    getLead: vi.fn(() => Promise.resolve({ data: {} })),
    getLeadDuplicates: vi.fn(() => Promise.resolve({ data: [] })),
    getLeadClientMatch: vi.fn(() => Promise.resolve({ data: [] })),
    getLeadPointsContact: vi.fn(() => Promise.resolve({ data: null })),
    getLeadJalonsDevis: vi.fn(() => Promise.resolve({ data: { results: [] } })),
    whatsappDevis: vi.fn(() => Promise.resolve({ data: {} })),
    logInteraction: vi.fn(() => Promise.resolve({ data: {} })),
    mergeLeads: vi.fn(() => Promise.resolve({ data: {} })),
    updateLead: vi.fn(() => Promise.resolve({ data: {} })),
    createLead: vi.fn(() => Promise.resolve({ data: { id: 1 } })),
    archiverLead: vi.fn(() => Promise.resolve({ data: {} })),
    restaurerLead: vi.fn(() => Promise.resolve({ data: {} })),
  },
}))
vi.mock('../../../lib/toast', async (importOriginal) => ({
  ...(await importOriginal()),
  toastWithUndo: vi.fn(),
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

const LEAD = { id: 1569, nom: 'ouissam merbahi', stage: 'FOLLOW_UP', is_archived: false }

beforeEach(() => { mockMatchMedia(false); try { localStorage.clear() } catch { /* noop */ } })
afterEach(() => { cleanup(); vi.clearAllMocks() })

function renderLead({ initialDevis = null, lead = LEAD, ...props } = {}) {
  const store = configureStore({ reducer: { crm: crmReducer, auth: (s = { user: { id: 4 } }) => s } })
  return render(
    <Provider store={store}>
      <MemoryRouter>
        <LeadWorkspace lead={lead} initialDevis={initialDevis} onClose={vi.fn()} onSaved={vi.fn()} {...props} />
      </MemoryRouter>
    </Provider>,
  )
}
const renderWithDevisPanel = () => renderLead({ initialDevis: 'edit' })

const archiverParLeMenu = async () => {
  fireEvent.keyDown(screen.getByRole('button', { name: /Plus d'actions/ }), { key: 'Enter' })
  fireEvent.click(await screen.findByRole('menuitem', { name: /Archiver/ }))
}

const flush = () => new Promise((r) => setTimeout(r, 0))

describe('Incident 02/10 — touches tapées dans le panneau devis ouvert depuis la fiche lead', () => {
  it('« a » dans le panneau devis n’archive JAMAIS le lead', async () => {
    const { findByTestId } = renderWithDevisPanel()
    const btn = await findByTestId('devis-btn')
    btn.focus()
    fireEvent.keyDown(btn, { key: 'a' })
    await flush()
    expect(crmApi.archiverLead).not.toHaveBeenCalled()
  })

  it('« j » dans le panneau devis ne fait JAMAIS changer la fiche de lead dessous', async () => {
    const onNavigateLead = vi.fn()
    const queue = [LEAD, { id: 1570, nom: 'suivant', stage: 'NEW' }]
    renderLead({ initialDevis: 'edit', leadsQueue: queue, onNavigateLead })
    const btn = await screen.findByTestId('devis-btn')
    btn.focus()
    fireEvent.keyDown(btn, { key: 'j' })
    await flush()
    expect(onNavigateLead).not.toHaveBeenCalled()
  })

  it('« 3 » dans le panneau devis ne change JAMAIS l’étape du lead', async () => {
    const { findByTestId } = renderWithDevisPanel()
    const btn = await findByTestId('devis-btn')
    btn.focus()
    fireEvent.keyDown(btn, { key: '3' })
    await flush()
    expect(crmApi.updateLead).not.toHaveBeenCalled()
  })
})

describe('Incident 02/10 — la fiche seule garde ses raccourcis, l’archivage est toujours demandé', () => {
  it('sans panneau par-dessus, « 2 » change toujours l’étape (la garde ne coupe pas tout)', async () => {
    // Lead au stade NEW : « 2 » est une AVANCÉE (pas de question de recul).
    renderLead({ lead: { ...LEAD, stage: 'NEW' } })
    fireEvent.keyDown(document, { key: '2' })
    await waitFor(() => expect(crmApi.updateLead).toHaveBeenCalledWith(1569, { stage: 'CONTACTED' }))
  })

  it('« a » sur la fiche seule n’archive plus le lead', async () => {
    renderLead()
    fireEvent.keyDown(document, { key: 'a' })
    await flush()
    expect(crmApi.archiverLead).not.toHaveBeenCalled()
  })

  it('archiver depuis le menu pose la question en NOMMANT le lead ; « Annuler » ne touche à rien', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false)
    renderLead()
    await archiverParLeMenu()
    await waitFor(() => expect(confirmSpy).toHaveBeenCalled())
    expect(confirmSpy.mock.calls[0][0]).toMatch(/pipeline/)
    await flush()
    expect(crmApi.archiverLead).not.toHaveBeenCalled()
    confirmSpy.mockRestore()
  })

  it('archivage confirmé → archive + toast « Annuler » qui restaure le lead', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)
    renderLead()
    await archiverParLeMenu()
    await waitFor(() => expect(crmApi.archiverLead).toHaveBeenCalledWith(1569))
    await waitFor(() => expect(toastWithUndo).toHaveBeenCalledTimes(1))
    const opts = toastWithUndo.mock.calls[0][0]
    expect(opts.message).toContain('ouissam merbahi')
    expect(opts.duration).toBeGreaterThanOrEqual(10000)
    opts.onUndo()
    await waitFor(() => expect(crmApi.restaurerLead).toHaveBeenCalledWith(1569))
    confirmSpy.mockRestore()
  })
})
