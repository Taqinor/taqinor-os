import { describe, it, expect, vi } from 'vitest'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { renderLeadWorkspace, makeStore } from '../../../test/leadWorkspaceHarness'
import { LEAD_A, installerHooksLeadWorkspace } from '../../../test/leadWorkspaceMocks'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import crmApi from '../../../api/crmApi'
import LeadWorkspace from './LeadWorkspace'
import { ConfirmProvider } from '../../../providers/ConfirmProvider'
import { PIPELINE_STAGES, STAGE_LABELS } from '../stages'

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

/* ORDRE FONDATEUR 2026-08-01 — « les leads doivent pouvoir REVENIR EN ARRIÈRE
   d'étape, avec une confirmation avant ». La question se pose dans la FENÊTRE
   lead, sur le chemin commun aux DEUX entrées du contrôle d'étape (menu LW16 et
   raccourcis « 1-4 » LW23) ; le moteur transporte la réponse (`confirme_recul`)
   jusqu'au PATCH, et une avancée reste un PATCH nu. Fenêtre, rails, moteur et
   boîte de confirmation RÉELS ; seul le réseau est simulé. */
describe('LW23/LW16 — reculer d’étape se confirme avant le PATCH', () => {
  const [, CONTACTED, QUOTE_SENT] = PIPELINE_STAGES
  const LEAD_AU_DEVIS = { ...LEAD_A, stage: QUOTE_SENT }
  const TITRE_RECUL = `Ramener « ${LEAD_A.nom} » de ${STAGE_LABELS[QUOTE_SENT]} à ${STAGE_LABELS[CONTACTED]} ?`

  function ouvrirAvecConfirmation(lead) {
    crmApi.getLead.mockResolvedValue({ data: lead })
    return render(
      <Provider store={makeStore()}>
        <MemoryRouter>
          <ConfirmProvider>
            <LeadWorkspace lead={lead} onClose={vi.fn()} onSaved={vi.fn()} />
          </ConfirmProvider>
        </MemoryRouter>
      </Provider>,
    )
  }

  it('une AVANCÉE part directement : aucune question, PATCH nu sans marqueur de recul', async () => {
    ouvrirAvecConfirmation(LEAD_A)
    fireEvent.keyDown(document, { key: '2' })
    await waitFor(() => expect(crmApi.updateLead).toHaveBeenCalledWith(1, { stage: CONTACTED }))
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
    expect(crmApi.updateLead.mock.calls[0][1]).not.toHaveProperty('confirme_recul')
  })

  it('un RECUL au clavier demande d’abord, en nommant le lead et les DEUX étapes', async () => {
    ouvrirAvecConfirmation(LEAD_AU_DEVIS)
    fireEvent.keyDown(document, { key: '2' })
    const dialogue = await screen.findByRole('alertdialog')
    expect(dialogue).toHaveTextContent(TITRE_RECUL)
    expect(crmApi.updateLead).not.toHaveBeenCalled()
  })

  it('« Ramener » (non destructif) envoie le PATCH avec confirme_recul: true', async () => {
    ouvrirAvecConfirmation(LEAD_AU_DEVIS)
    fireEvent.keyDown(document, { key: '2' })
    const ramener = await screen.findByRole('button', { name: 'Ramener' })
    // Rien n’est supprimé : on remonte le pipeline, pas de rouge d’alerte.
    expect(ramener.className).not.toContain('destructive')
    fireEvent.click(ramener)
    await waitFor(() => expect(crmApi.updateLead).toHaveBeenCalledWith(
      1, { stage: CONTACTED, confirme_recul: true },
    ))
  })

  it('« Annuler » ne touche à rien : aucun PATCH, la boîte se ferme', async () => {
    ouvrirAvecConfirmation(LEAD_AU_DEVIS)
    fireEvent.keyDown(document, { key: '2' })
    fireEvent.click(await screen.findByRole('button', { name: 'Annuler' }))
    await waitFor(() => expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument())
    expect(crmApi.updateLead).not.toHaveBeenCalled()
  })

  it('le MENU d’étape passe par la même question que les raccourcis (un seul chemin)', async () => {
    ouvrirAvecConfirmation(LEAD_AU_DEVIS)
    fireEvent.keyDown(document.querySelector('.lw-stagepill'), { key: 'Enter' })
    fireEvent.click(await screen.findByRole('menuitem', { name: STAGE_LABELS[CONTACTED] }))
    const dialogue = await screen.findByRole('alertdialog')
    expect(dialogue).toHaveTextContent(TITRE_RECUL)
    expect(crmApi.updateLead).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'Ramener' }))
    await waitFor(() => expect(crmApi.updateLead).toHaveBeenCalledWith(
      1, { stage: CONTACTED, confirme_recul: true },
    ))
  })
})
