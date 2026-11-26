import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { renderLeadWorkspace } from '../../../test/leadWorkspaceHarness'
import { installerHooksLeadWorkspace } from '../../../test/leadWorkspaceMocks'
import { waitFor, act, screen, fireEvent } from '@testing-library/react'
import { signalerNotificationsRecues } from '../../../lib/evenementsNotification'
import { HISTORIQUE_INTERVALLE_MS } from './useHistoriqueLead'
import api from '../../../api/axios'
import crmApi from '../../../api/crmApi'

// Historique du lead (fondateur, prod : « i dont see this ») — LW41 économisait la requête `/historique/` quand le GET
// détail embarquait `chatter_recent` ; mais `chatter_recent` est figé à l'ouverture : ce que le CLIENT fait ensuite (demande
// de rappel depuis la page devis…) n'apparaissait jamais sur une fiche ouverte. Désormais `chatter_recent` ne sert que le
// premier rendu : l'historique est TOUJOURS relu à l'ouverture, au retour au premier plan, à intervalle calme et à
// l'arrivée d'une notification de CE lead — sans toucher au composer ni vider la liste sur un échec.

vi.mock('../../../pages/crm/leads/LeadDevisPanel', () => ({ default: () => null }))
vi.mock('../../../pages/crm/leads/SigneDialog', () => ({ default: () => null }))
// Le rail de contexte RÉEL (onglet Historique + composer), enfants réseau neutralisés.
vi.mock('./ContextRail', async () => {
  const { default: TimelineTab } = await import('./TimelineTab')
  return { default: (p) => (
    <TimelineTab state={p.state} historique={p.historique} refreshHistorique={p.refreshHistorique}
      composer={p.state.composer} setComposer={(patch) => p.dispatch({ type: 'SET_COMPOSER', patch })}
      resetComposer={() => p.dispatch({ type: 'RESET_COMPOSER' })} />
  ) }
})
vi.mock('./IdentityRail', () => ({ default: () => <div data-testid="identity-rail" /> }))

vi.mock('../../../api/crmApi', async () => (await import('../../../test/leadWorkspaceMocks')).crmApiLeadWorkspace({
  getLead: vi.fn(() => Promise.resolve({ data: { id: 1 } })),
  getLeadPhotoToit: vi.fn(() => Promise.resolve({ data: { visite_id: null, url: null, texture_calage: null } })),
  villeStatut: vi.fn(() => Promise.resolve({ data: { statut: 'connue' } })),
}))

installerHooksLeadWorkspace()

function renderEdit(lead) {
  return renderLeadWorkspace({ lead }, 42, { role: 'admin' })
}

const note = (id, body, created_at) => ({ id, kind: 'note', body, user_nom: 'Sami', created_at })
const ancienne = note(9, 'Déjà là', '2026-11-26T08:00:00Z')
const rappel = note(10, 'Le client demande à être contacté (DEV-1)', '2026-11-26T09:00:00Z')
const leadAvecChatter = { id: 1, nom: 'Ali', prenom: 'Ben', stage: 'NEW', is_archived: false, chatter_recent: [ancienne] }
const appelsHistorique = () => api.get.mock.calls.filter(([u]) => u === '/crm/leads/1/historique/').length

afterEach(() => { vi.useRealTimers() })
beforeEach(() => { crmApi.getLead.mockResolvedValue({ data: leadAvecChatter }) })

describe('Historique du lead — relu sur une fiche ouverte', () => {
  it('chatter_recent non vide : le GET /historique/ part QUAND MÊME à l’ouverture', async () => {
    renderEdit(leadAvecChatter)
    await waitFor(() => expect(api.get).toHaveBeenCalledWith('/crm/leads/1/historique/'))
  })

  it('lead ouvert SANS chatter_recent : le GET /historique/ part aussi', async () => {
    renderEdit({ id: 1, nom: 'Ali', prenom: 'Ben', stage: 'NEW', is_archived: false, chatter_recent: [] })
    await waitFor(() => expect(api.get).toHaveBeenCalledWith('/crm/leads/1/historique/'))
  })

  it('une entrée apparue côté serveur après l’ouverture se voit au retour de la fenêtre, composer intact', async () => {
    api.get.mockImplementation((u) => Promise.resolve({ data: u === '/crm/leads/1/historique/' ? [ancienne] : [] }))
    renderEdit(leadAvecChatter)
    await screen.findAllByText(/Déjà là/)
    const zone = screen.getByPlaceholderText(/Écrire une note/)
    fireEvent.change(zone, { target: { value: 'ma note en cours' } })
    api.get.mockImplementation((u) => Promise.resolve({ data: u === '/crm/leads/1/historique/' ? [rappel, ancienne] : [] }))
    act(() => { window.dispatchEvent(new Event('focus')) })
    await screen.findAllByText(/demande à être contacté/)
    expect(screen.getByPlaceholderText(/Écrire une note/).value).toBe('ma note en cours')
    expect(screen.getAllByText(/Déjà là/).length).toBeGreaterThan(0)
  })

  it('à intervalle calme (même cadence que la cloche) : la nouvelle entrée apparaît', async () => {
    vi.useFakeTimers()
    api.get.mockImplementation((u) => Promise.resolve({ data: u === '/crm/leads/1/historique/' ? [ancienne] : [] }))
    renderEdit(leadAvecChatter)
    await act(async () => { await vi.advanceTimersByTimeAsync(10) })
    const avant = appelsHistorique()
    api.get.mockImplementation((u) => Promise.resolve({ data: u === '/crm/leads/1/historique/' ? [rappel, ancienne] : [] }))
    await act(async () => { await vi.advanceTimersByTimeAsync(HISTORIQUE_INTERVALLE_MS + 50) })
    expect(appelsHistorique()).toBeGreaterThan(avant)
    expect(screen.getAllByText(/demande à être contacté/).length).toBeGreaterThan(0)
  })

  it('une notification NON LUE de ce lead relit tout de suite ; celle d’un autre lead, non', async () => {
    api.get.mockImplementation((u) => Promise.resolve({ data: u === '/crm/leads/1/historique/' ? [ancienne] : [] }))
    renderEdit(leadAvecChatter)
    await screen.findAllByText(/Déjà là/)
    const n = appelsHistorique()
    act(() => { signalerNotificationsRecues(['/crm/leads?lead=2']) })
    await new Promise((r) => { setTimeout(r, 20) })
    expect(appelsHistorique()).toBe(n)
    api.get.mockImplementation((u) => Promise.resolve({ data: u === '/crm/leads/1/historique/' ? [rappel, ancienne] : [] }))
    act(() => { signalerNotificationsRecues(['/crm/leads?lead=1']) })
    await screen.findAllByText(/demande à être contacté/)
  })

  it('une relecture en échec ne vide jamais la liste affichée', async () => {
    api.get.mockImplementation((u) => Promise.resolve({ data: u === '/crm/leads/1/historique/' ? [ancienne] : [] }))
    renderEdit(leadAvecChatter)
    await screen.findAllByText(/Déjà là/)
    api.get.mockImplementation((u) => (u === '/crm/leads/1/historique/'
      ? Promise.reject(new Error('503')) : Promise.resolve({ data: [] })))
    const n = appelsHistorique()
    act(() => { window.dispatchEvent(new Event('focus')) })
    await waitFor(() => expect(appelsHistorique()).toBeGreaterThan(n))
    await new Promise((r) => { setTimeout(r, 20) })
    expect(screen.getAllByText(/Déjà là/).length).toBeGreaterThan(0)
  })

  it('une seule lecture en vol par lead : deux déclencheurs passifs de suite = une requête', async () => {
    let fin
    api.get.mockImplementation((u) => (u === '/crm/leads/1/historique/'
      ? new Promise((r) => { fin = () => r({ data: [ancienne] }) }) : Promise.resolve({ data: [] })))
    renderEdit(leadAvecChatter)
    await waitFor(() => expect(appelsHistorique()).toBe(1))
    act(() => { window.dispatchEvent(new Event('focus')); window.dispatchEvent(new Event('focus')) })
    expect(appelsHistorique()).toBe(1)
    await act(async () => { fin() })
  })
})
