// CAD51 — « Relancer la cadence » ne tue plus une cadence en cours en silence.
// Le serveur refuse (409) tant que l'arrêt n'est pas confirmé et NOMME ce qui
// serait perdu ; l'écran le dit, exige un motif, puis relance. Réponses et
// corps = le contrat COMMITTÉ `apps/crm/contract_samples/lead_relance_initialiser.json`
// (PACT10) — jamais un objet retapé.
import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { documentContrat } from '../../../../test/fixtures/contractSamples'
import { initState } from '../draftCore'
import SectionPipeline from './SectionPipeline'

vi.mock('../../../../api/crmApi', () => ({
  default: {
    initialiserRelance: vi.fn(),
    arreterCadence: vi.fn(),
    getRelanceEtapesLead: vi.fn(() => Promise.resolve({ data: { count: 0, results: [] } })),
    getCanaux: vi.fn(() => Promise.resolve({ data: [] })),
  },
}))
vi.mock('../../../../ui/confirm', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
  toastPromise: vi.fn((p) => p),
}))

import crmApi from '../../../../api/crmApi'
import { toast } from '../../../../ui/confirm'

const CONTRAT = documentContrat('crm', 'lead_relance_initialiser')
const REF_DATA = { users: [], tagOptions: [], motifOptions: [] }

afterEach(() => { cleanup(); vi.clearAllMocks() })

function renderSection() {
  const state = initState({ lead: { id: 77 }, mode: 'edit' })
  return render(
    <SectionPipeline state={state} setField={vi.fn()} errors={{}} refData={REF_DATA} />,
  )
}

const refus = (status, data) => Promise.reject({ response: { status, data } })

describe('CAD51 — relancer une cadence plus prioritaire exige une confirmation', () => {
  it('le 409 affiche ce qui sera arrêté, sans toast de succès ni d’erreur', async () => {
    const user = userEvent.setup()
    crmApi.initialiserRelance.mockImplementationOnce(() => refus(409, CONTRAT.exemple))
    renderSection()

    await user.click(screen.getByTestId('lf-relance-cadence'))

    const panneau = await screen.findByTestId('cad51-confirmer-remplacement')
    expect(crmApi.initialiserRelance.mock.calls[0][1]).toEqual(CONTRAT.corps)
    expect(panneau.textContent).toContain(CONTRAT.exemple.detail)
    // La cadence arrêtée est nommée sur le bouton même de la confirmation.
    const libelle = CONTRAT.exemple.remplacement.cadences_arretees_libelles[0]
    expect(screen.getByTestId('lf-relance-confirmer').textContent).toContain(libelle)
    expect(toast.success).not.toHaveBeenCalled()
    expect(toast.error).not.toHaveBeenCalled()
  })

  it('sans motif, « Arrêter et relancer » reste désactivé', async () => {
    const user = userEvent.setup()
    crmApi.initialiserRelance.mockImplementationOnce(() => refus(409, CONTRAT.exemple))
    renderSection()
    await user.click(screen.getByTestId('lf-relance-cadence'))
    expect(await screen.findByTestId('lf-relance-confirmer')).toBeDisabled()
    expect(crmApi.initialiserRelance).toHaveBeenCalledTimes(1)
  })

  it('avec un motif, la confirmation part dans le corps du contrat puis relance', async () => {
    const user = userEvent.setup()
    crmApi.initialiserRelance
      .mockImplementationOnce(() => refus(409, CONTRAT.exemple))
      .mockImplementationOnce(() => Promise.resolve({ data: [{ id: 1, cadence: 'contact' }] }))
    renderSection()

    await user.click(screen.getByTestId('lf-relance-cadence'))
    await user.type(await screen.findByTestId('lf-remplacement-motif'), CONTRAT.corps_confirme.motif)
    await user.click(screen.getByTestId('lf-relance-confirmer'))

    await waitFor(() => expect(crmApi.initialiserRelance).toHaveBeenCalledTimes(2))
    const [lead, corps, config] = crmApi.initialiserRelance.mock.calls[1]
    expect(lead).toBe(77)
    expect(corps).toEqual(CONTRAT.corps_confirme)
    expect(config).toEqual({ suppressErrorToast: true })
    await waitFor(() => expect(toast.success).toHaveBeenCalledTimes(1))
    expect(screen.queryByTestId('lf-relance-confirmation')).toBeNull()
  })

  it('un 400 « motif obligatoire » s’affiche SOUS le champ motif, le panneau reste', async () => {
    const user = userEvent.setup()
    crmApi.initialiserRelance
      .mockImplementationOnce(() => refus(409, CONTRAT.exemple))
      .mockImplementationOnce(() => refus(400, CONTRAT.exemple_erreur_motif))
    renderSection()

    await user.click(screen.getByTestId('lf-relance-cadence'))
    await user.type(await screen.findByTestId('lf-remplacement-motif'), 'x')
    await user.click(screen.getByTestId('lf-relance-confirmer'))

    const erreur = await screen.findByText(CONTRAT.exemple_erreur_motif.erreurs.motif[0])
    expect(erreur.closest('[role="alert"]')).not.toBeNull()
    const panneau = screen.getByTestId('cad51-confirmer-remplacement')
    expect(panneau.textContent).toContain(CONTRAT.exemple.detail)
    expect(screen.getByTestId('lf-remplacement-motif')).toHaveAttribute('aria-invalid', 'true')
    expect(toast.error).not.toHaveBeenCalled()
  })

  it('« Annuler » ferme la confirmation sans rien relancer', async () => {
    const user = userEvent.setup()
    crmApi.initialiserRelance.mockImplementationOnce(() => refus(409, CONTRAT.exemple))
    renderSection()
    await user.click(screen.getByTestId('lf-relance-cadence'))
    const panneau = await screen.findByTestId('lf-relance-confirmation')
    await user.click(
      [...panneau.querySelectorAll('button')].find((b) => b.textContent.trim() === 'Annuler'),
    )
    expect(screen.queryByTestId('lf-relance-confirmation')).toBeNull()
    expect(crmApi.initialiserRelance).toHaveBeenCalledTimes(1)
  })
})
