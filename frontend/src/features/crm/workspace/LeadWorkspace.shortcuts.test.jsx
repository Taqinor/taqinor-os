import { describe, it, expect, vi } from 'vitest'
import { renderLeadWorkspace } from '../../../test/leadWorkspaceHarness'
import { LEAD_A, installerHooksLeadWorkspace } from '../../../test/leadWorkspaceMocks'
import { fireEvent, waitFor } from '@testing-library/react'
import crmApi from '../../../api/crmApi'

/* LW23 — mode ÉDITION : registre de raccourcis propre (a/d/n/1-4). Mêmes
   neutralisations que LeadWorkspaceCreate.test.jsx (les satellites/rails ne
   sont PAS encore construits par les autres lanes — on teste le CÂBLAGE de
   cette lane, pas leur contenu). */
vi.mock('../../../pages/crm/leads/LeadDevisPanel', () => ({ default: () => null }))
vi.mock('../../../pages/crm/leads/SigneDialog', () => ({ default: () => null }))

vi.mock('../../../api/crmApi', async () => (await import('../../../test/leadWorkspaceMocks')).crmApiLeadWorkspace())


installerHooksLeadWorkspace()

function renderEdit(lead = LEAD_A) {
  return renderLeadWorkspace({ lead })
}

describe('LW23 — raccourcis propres (d/n/1-4)', () => {
  it('« a » n’archive PLUS le lead (incident 02/10/2026 — archiver est toujours confirmé)', async () => {
    renderEdit()
    fireEvent.keyDown(document, { key: 'a' })
    await new Promise((r) => setTimeout(r, 0))
    expect(crmApi.archiverLead).not.toHaveBeenCalled()
  })

  it('« d » focus le picker Responsable (hook DOM stable .ap-trigger, une autre lane)', () => {
    renderEdit()
    // Simule le hook DOM que l'IdentityRail (LW14-18, autre lane) posera —
    // cette lane ne dépend QUE de la classe stable, jamais de son contenu.
    // Posé DANS le contenu du Dialog (le focus-trap Radix refuse de sortir
    // du contenu de la boîte de dialogue — un nœud posé hors de celle-ci ne
    // pourrait de toute façon jamais recevoir le focus réel).
    const trigger = document.createElement('button')
    trigger.className = 'ap-trigger'
    document.querySelector('[role="dialog"]').appendChild(trigger)
    fireEvent.keyDown(document, { key: 'd' })
    expect(document.activeElement).toBe(trigger)
    trigger.remove()
  })

  it('« n » émet lw:open-note-composer avec le leadId (ContextRail — LW19-21 — doit écouter)', () => {
    renderEdit()
    const onEvt = vi.fn()
    window.addEventListener('lw:open-note-composer', onEvt)
    fireEvent.keyDown(document, { key: 'n' })
    expect(onEvt).toHaveBeenCalledTimes(1)
    expect(onEvt.mock.calls[0][0].detail).toEqual({ leadId: 1 })
    window.removeEventListener('lw:open-note-composer', onEvt)
  })

  it('« 2 » change l’étape vers CONTACTED (jamais SIGNED/COLD à une touche)', async () => {
    renderEdit()
    fireEvent.keyDown(document, { key: '2' })
    await waitFor(() => expect(crmApi.updateLead).toHaveBeenCalledWith(1, { stage: 'CONTACTED' }))
  })

  it('mode création (pas de lead) : les raccourcis sont désactivés (enabled=false)', async () => {
    renderEdit(null)
    fireEvent.keyDown(document, { key: '2' })
    await new Promise((r) => setTimeout(r, 0))
    expect(crmApi.updateLead).not.toHaveBeenCalled()
  })
})
