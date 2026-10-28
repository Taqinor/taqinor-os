import { describe, it, expect, vi } from 'vitest'
import { renderLeadWorkspace } from '../../../test/leadWorkspaceHarness'
import { installerHooksLeadWorkspace } from '../../../test/leadWorkspaceMocks'
import { waitFor } from '@testing-library/react'
import api from '../../../api/axios'
import crmApi from '../../../api/crmApi'

// LW41 — `chatter_recent` doit vraiment économiser la requête historique. Avant
// ce fix, le shell appelait TOUJOURS `/historique/` au montage même si le GET
// détail embarquait déjà `chatter_recent` (LW30) — l'ouverture coûtait PLUS
// cher qu'avant, pas moins.

vi.mock('../../../pages/crm/leads/LeadDevisPanel', () => ({ default: () => null }))
vi.mock('../../../pages/crm/leads/SigneDialog', () => ({ default: () => null }))
vi.mock('./ContextRail', () => ({ default: () => null }))
vi.mock('./IdentityRail', () => ({ default: () => <div data-testid="identity-rail" /> }))

vi.mock('../../../api/crmApi', async () => (await import('../../../test/leadWorkspaceMocks')).crmApiLeadWorkspace({
  getLead: vi.fn(() => Promise.resolve({ data: { id: 1 } })),
}))

installerHooksLeadWorkspace()

function renderEdit(lead) {
  return renderLeadWorkspace({ lead })
}

describe('LW41 — pas de double requête historique quand chatter_recent est déjà là', () => {
  it('lead ouvert avec chatter_recent non-vide → AUCUN GET /historique/', async () => {
    const lead = {
      id: 1, nom: 'Ali', prenom: 'Ben', stage: 'NEW', is_archived: false,
      chatter_recent: [{ id: 9, kind: 'note', body: 'Déjà là', user_nom: 'Sami', created_at: new Date().toISOString() }],
    }
    renderEdit(lead)
    // Laisse les effets/microtasks s'écouler.
    await waitFor(() => expect(crmApi.getAssignableUsers).toHaveBeenCalled())
    expect(api.get).not.toHaveBeenCalledWith('/crm/leads/1/historique/')
  })

  it('lead ouvert SANS chatter_recent (absent/vide) → le GET /historique/ part toujours', async () => {
    const lead = { id: 1, nom: 'Ali', prenom: 'Ben', stage: 'NEW', is_archived: false, chatter_recent: [] }
    renderEdit(lead)
    await waitFor(() => expect(api.get).toHaveBeenCalledWith('/crm/leads/1/historique/'))
  })
})
