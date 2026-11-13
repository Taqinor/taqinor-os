import { describe, it, expect, vi } from 'vitest'
import { renderLeadWorkspace } from '../../../test/leadWorkspaceHarness'
import { LEAD_A, installerHooksLeadWorkspace } from '../../../test/leadWorkspaceMocks'
import { screen, fireEvent, waitFor } from '@testing-library/react'
import { toast } from 'sonner'
import crmApi from '../../../api/crmApi'

/* LW16-wire — le contrat `onAction` du rail (IdentityRail/StageControl, lane 2)
   gagne deux cas : 'set-field' (édition rapide responsable/relance) et
   'change-stage' (StageControl, transitions non-SIGNED — passe par le MÊME
   moteur `changeStage` que le raccourci clavier « 1-4 », LW23), avec un toast
   d'erreur unique côté moteur (useLeadDraft.js) sur un recul de funnel (400). */
vi.mock('sonner', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, toast: { ...actual.toast, error: vi.fn(), success: vi.fn() } }
})

vi.mock('../../../pages/crm/leads/LeadDevisPanel', () => ({
  default: () => <div data-testid="panneau-devis" />,
}))
vi.mock('../../../pages/crm/leads/SigneDialog', () => ({ default: () => null }))

// IdentityRail réel n'est encore qu'un placeholder (LW14-18 pas construit) —
// on l'intercepte pour exposer le contrat `onAction` à des boutons de test,
// EXACTEMENT le patron déjà établi (AssigneePicker/CustomFieldsInput ci-dessus).
vi.mock('./IdentityRail', async () => (await import('../../../test/leadWorkspaceMocks'))
  .identityRailMock([
    [['set-field', { key: 'owner', value: '7' }], 'set-field-owner'],
    [['change-stage', 'CONTACTED'], 'change-stage-contacted'],
    [['set-field', { key: 'batterie_souhaitee', value: 'les_deux' }], 'set-field-batterie'],
    [['open-devis', 'auto'], 'open-devis-auto'],
    [['relance-arreter'], 'relance-arreter'],
  ]))

vi.mock('../../../api/crmApi', async () => (await import('../../../test/leadWorkspaceMocks')).crmApiLeadWorkspace())


installerHooksLeadWorkspace()

function renderEdit(lead = LEAD_A) {
  return renderLeadWorkspace({ lead })
}

describe("LW16-wire — onAction('set-field'/'change-stage')", () => {
  it("'set-field' pousse la valeur dans le draft (autosauvegarde débouncée, comme toute frappe)", () => {
    renderEdit()
    fireEvent.click(screen.getByText('set-field-owner'))
    // Pas de PATCH immédiat (débounce 1.5s) — c'est du SET_FIELD, pas un
    // point-write : la preuve est l'ABSENCE d'appel synchrone à updateLead.
    expect(crmApi.updateLead).not.toHaveBeenCalled()
  })

  it("'change-stage' appelle le même moteur que le raccourci clavier « 2 » (PATCH {stage})", async () => {
    renderEdit()
    fireEvent.click(screen.getByText('change-stage-contacted'))
    await waitFor(() => expect(crmApi.updateLead).toHaveBeenCalledWith(1, { stage: 'CONTACTED' }))
  })

  // LW42 — CONTRAT MIS À JOUR. Avant : un toast FIXE « Retour d'étape non
  // autorisé » pour TOUT 400 (donc un message faux pour un lead perdu
  // verrouillé), et SILENCE total hors-400 (un clic hors-ligne ne disait rien).
  // Les deux étaient les bugs décrits par LW42 ; ces tests actent le nouveau
  // comportement, ils ne l'assouplissent pas.
  it('un recul de funnel refusé (400) surface le VRAI message serveur, une seule fois', async () => {
    crmApi.updateLead.mockRejectedValueOnce({ response: { status: 400, data: { detail: 'stage backward' } } })
    renderEdit()
    fireEvent.click(screen.getByText('change-stage-contacted'))
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith('stage backward'))
    expect(toast.error).toHaveBeenCalledTimes(1)
  })

  // DEV-202611-0061 (13/11/2026) — choix batterie changé puis « devis
  // automatique » 1 s après : le devis partait avant l'autosauvegarde et le
  // serveur lisait l'ancien choix. Le panneau (qui crée le devis) n'ouvre
  // qu'APRÈS l'enregistrement de la fiche.
  it("'open-devis' attend l'enregistrement de la fiche avant d'ouvrir le panneau devis", async () => {
    let resoudre
    crmApi.updateLead.mockImplementationOnce(() => new Promise((r) => { resoudre = r }))
    renderEdit()
    fireEvent.click(screen.getByText('set-field-batterie'))
    fireEvent.click(screen.getByText('open-devis-auto'))
    await waitFor(() => expect(crmApi.updateLead).toHaveBeenCalledWith(
      1, expect.objectContaining({ batterie_souhaitee: 'les_deux' })))
    expect(screen.queryByTestId('panneau-devis')).toBeNull()
    resoudre({ data: { id: 1, batterie_souhaitee: 'les_deux' } })
    expect(await screen.findByTestId('panneau-devis')).toBeTruthy()
  })

  it('fiche déjà enregistrée : le panneau devis s’ouvre tout de suite, sans PATCH', async () => {
    renderEdit()
    fireEvent.click(screen.getByText('open-devis-auto'))
    expect(await screen.findByTestId('panneau-devis')).toBeTruthy()
    expect(crmApi.updateLead).not.toHaveBeenCalled()
  })

  it('une autre erreur (réseau/500) n’est plus muette : toast générique distinct', async () => {
    crmApi.updateLead.mockRejectedValueOnce({ response: { status: 500 } })
    renderEdit()
    fireEvent.click(screen.getByText('change-stage-contacted'))
    await waitFor(() => expect(crmApi.updateLead).toHaveBeenCalled())
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Échec du changement d'étape — réessayez."))
    expect(toast.error).toHaveBeenCalledTimes(1)
  })
})

describe("AERR117 — onAction('relance-arreter') : boîte maison, aucun window.prompt", () => {
  it('ouvre une boîte « Motif », puis arrête la cadence avec ce motif', async () => {
    const prompt = vi.spyOn(window, 'prompt')
    crmApi.arreterCadence = vi.fn(() => Promise.resolve({ data: {} }))
    renderEdit()
    fireEvent.click(screen.getByText('relance-arreter'))
    const champ = await screen.findByLabelText("Motif d'arrêt de la cadence")
    fireEvent.change(champ, { target: { value: 'Client injoignable' } })
    fireEvent.click(screen.getByRole('button', { name: 'Valider' }))
    await waitFor(() => expect(crmApi.arreterCadence).toHaveBeenCalledWith(1, { motif: 'Client injoignable' }))
    expect(prompt).not.toHaveBeenCalled()
    prompt.mockRestore()
  })
})
