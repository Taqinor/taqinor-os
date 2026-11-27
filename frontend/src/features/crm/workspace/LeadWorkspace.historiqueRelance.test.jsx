import { describe, it, expect, vi } from 'vitest'
import { renderLeadWorkspace } from '../../../test/leadWorkspaceHarness'
import { installerHooksLeadWorkspace } from '../../../test/leadWorkspaceMocks'
import { waitFor, act, screen } from '@testing-library/react'
import api from '../../../api/axios'
import crmApi from '../../../api/crmApi'

// ERR-QAH-CRM-HISTORIQUE-VIDE-RELANCE — après l'autosave de « Relance le », le
// panneau « Historique » affichait « Aucune activité pour le moment. » : la
// réponse du PATCH (sérialiseur d'écriture) n'embarque pas `chatter_recent`,
// qui était donc EFFACÉ de `state.server`, et `/historique/` n'était jamais
// relu. On prouve : (1) après un autosave réussi, `/historique/` est relu ;
// (2) `chatter_recent` survit à la réponse du PATCH.

vi.mock('../../../pages/crm/leads/LeadDevisPanel', () => ({ default: () => null }))
vi.mock('../../../pages/crm/leads/SigneDialog', () => ({ default: () => null }))
// Rail de contexte RÉEL (onglet Historique) : on doit VOIR la ligne relue.
vi.mock('./ContextRail', async () => {
  const { default: TimelineTab } = await import('./TimelineTab')
  return { default: (p) => (
    <TimelineTab state={p.state} historique={p.historique} refreshHistorique={p.refreshHistorique}
      composer={p.state.composer} setComposer={(patch) => p.dispatch({ type: 'SET_COMPOSER', patch })}
      resetComposer={() => p.dispatch({ type: 'RESET_COMPOSER' })} />
  ) }
})
// Le rail capture `onAction` : c'est par lui que « Relance le » écrit
// (onAction('set-field', { key: 'relance_date', … })).
let railOnAction = null
let railServer = null
vi.mock('./IdentityRail', () => ({
  default: ({ onAction, state }) => {
    railOnAction = onAction
    railServer = state?.server
    return <div data-testid="identity-rail" />
  },
}))

vi.mock('../../../api/crmApi', async () => (await import('../../../test/leadWorkspaceMocks')).crmApiLeadWorkspace({
  getLead: vi.fn(() => Promise.resolve({ data: { id: 1 } })),
  // Sérialiseur d'ÉCRITURE : PAS de `chatter_recent` dans la réponse.
  updateLead: vi.fn((id, corps) => Promise.resolve({ data: { id, nom: 'Ali', stage: 'NEW', ...corps } })),
}))

installerHooksLeadWorkspace()

function renderEdit(lead) {
  return renderLeadWorkspace({ lead })
}

describe('ERR-QAH-CRM-HISTORIQUE-VIDE-RELANCE — l’historique survit à l’autosave', () => {
  it('« Relance le » enregistré → /historique/ relu et chatter_recent conservé', async () => {
    const ancienne = { id: 9, kind: 'note', body: 'Déjà là', user_nom: 'Sami', created_at: new Date().toISOString() }
    const lead = {
      id: 1, nom: 'Ali', prenom: 'Ben', stage: 'NEW', is_archived: false,
      chatter_recent: [ancienne],
    }
    renderEdit(lead)
    await waitFor(() => expect(railOnAction).toBeTypeOf('function'))
    // Historique du lead : l'historique est relu dès l'ouverture ; on compte donc les lectures AVANT le geste.
    await waitFor(() => expect(api.get).toHaveBeenCalledWith('/crm/leads/1/historique/'))
    const avant = api.get.mock.calls.filter(([u]) => u === '/crm/leads/1/historique/').length

    act(() => { railOnAction('set-field', { key: 'relance_date', value: '2026-10-15T09:00' }) })

    await waitFor(() => expect(crmApi.updateLead).toHaveBeenCalled(), { timeout: 5000 })
    await waitFor(() => expect(
      api.get.mock.calls.filter(([u]) => u === '/crm/leads/1/historique/').length).toBeGreaterThan(avant), { timeout: 5000 })
    expect(railServer?.chatter_recent).toEqual([ancienne])
  })

  // R8-N1 — « prochaine touche ramenée » : le geste (frise / panneau d'appel / « Relance le »
  // sur cadence) rafraîchit la fiche par onAction('refresh') ou ('cadence-refresh') ; l'historique
  // doit être relu UNE fois et montrer la ligne écrite par le serveur, sans rechargement.
  it.each(['refresh', 'cadence-refresh'])('R8-N1 — onAction(%s) relit /historique/ une fois et montre la ligne', async (geste) => {
    const ancienne = { id: 9, kind: 'note', body: 'Déjà là', user_nom: 'Sami', created_at: '2026-11-26T08:00:00Z' }
    const nouvelle = { id: 10, kind: 'note', body: 'Prochaine touche ramenée', user_nom: 'Sami', created_at: '2026-11-27T09:30:00Z' }
    const url = '/crm/leads/1/historique/'
    const appels = () => api.get.mock.calls.filter(([u]) => u === url).length
    api.get.mockImplementation((u) => Promise.resolve({ data: u === url ? [ancienne] : [] }))
    renderEdit({ id: 1, nom: 'Ali', prenom: 'Ben', stage: 'NEW', is_archived: false, chatter_recent: [ancienne] })
    await screen.findAllByText(/Déjà là/)
    await waitFor(() => expect(railOnAction).toBeTypeOf('function'))
    const avant = appels()
    api.get.mockImplementation((u) => Promise.resolve({ data: u === url ? [nouvelle, ancienne] : [] }))
    act(() => { railOnAction(geste) })
    await screen.findAllByText(/Prochaine touche ramenée/)
    expect(appels()).toBe(avant + 1)
  })

  // Un `refresh` générique (devis, rail, appel…) ne change pas la relance : la fiche et l'historique
  // sont relus UNE fois, rien de ce qui dépend de `relanceVersion` (frise, étapes) n'est relu.
  it('un refresh générique : historique +1, fiche +1, frise/étapes inchangées ; cadence-refresh relit la frise', async () => {
    const url = '/crm/leads/1/historique/'
    const hist = () => api.get.mock.calls.filter(([u]) => u === url).length
    api.get.mockImplementation((u) => Promise.resolve({ data: u === url ? [] : [] }))
    renderEdit({ id: 1, nom: 'Ali', prenom: 'Ben', stage: 'NEW', is_archived: false, chatter_recent: [] })
    await waitFor(() => expect(railOnAction).toBeTypeOf('function'))
    await waitFor(() => expect(crmApi.getRelanceEtapesLead).toHaveBeenCalled())
    await new Promise((r) => { setTimeout(r, 50) })
    const h0 = hist(); const f0 = crmApi.getLead.mock.calls.length; const e0 = crmApi.getRelanceEtapesLead.mock.calls.length
    act(() => { railOnAction('refresh') })
    await waitFor(() => expect(hist()).toBe(h0 + 1))
    await new Promise((r) => { setTimeout(r, 100) })
    expect(hist()).toBe(h0 + 1)
    expect(crmApi.getLead.mock.calls.length).toBe(f0 + 1)
    expect(crmApi.getRelanceEtapesLead.mock.calls.length).toBe(e0)
    act(() => { railOnAction('cadence-refresh') })
    await waitFor(() => expect(crmApi.getRelanceEtapesLead.mock.calls.length).toBeGreaterThan(e0))
  })
})
