// CAD55 — « Relancer la cadence — Après devis » depuis la fiche cite le devis.
// Plusieurs devis envoyés → « lequel ? » en une ligne (le plus récent proposé) ;
// aucun → l'avertissement AVANT le lancement, « Lancer sans devis » explicite.
// Réponses et corps = le contrat COMMITTÉ
// `apps/crm/contract_samples/lead_relance_initialiser.json` (PACT10).
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

const refus = (status, data) => Promise.reject({ response: { status, data } })

async function relancerApresDevis(user) {
  const state = initState({ lead: { id: 77 }, mode: 'edit' })
  render(<SectionPipeline state={state} setField={vi.fn()} errors={{}} refData={REF_DATA} />)
  await user.selectOptions(screen.getByLabelText('Cadence à relancer'), 'apres_devis')
  await user.click(screen.getByTestId('lf-relance-cadence'))
}

describe('CAD55 — « Après devis » depuis la fiche rattache le devis', () => {
  it('plusieurs devis : la question en une ligne, le plus récent proposé, la réponse part en `devis`', async () => {
    const user = userEvent.setup()
    const question = CONTRAT.exemple_devis_a_choisir
    crmApi.initialiserRelance
      .mockImplementationOnce(() => refus(409, question))
      .mockImplementationOnce(() => Promise.resolve({ data: [{ id: 1, devis: 903 }] }))
    await relancerApresDevis(user)

    expect(crmApi.initialiserRelance.mock.calls[0][1]).toEqual(CONTRAT.corps_apres_devis)
    const bloc = await screen.findByTestId('cad55-choix-devis')
    expect(bloc.textContent).toContain(question.erreurs.devis[0])
    const choix = screen.getByLabelText('Devis cité par le suivi')
    expect(choix).toHaveValue(String(question.devis_a_choisir.propose))
    const [recent, ancien] = question.devis_a_choisir.choix
    expect(choix.textContent).toContain(recent.reference)
    expect(choix.textContent).toContain('envoyé le 12/09/2026')
    expect(toast.error).not.toHaveBeenCalled()

    // Sans rien changer : c'est le devis proposé qui part — le corps du contrat.
    await user.click(screen.getByTestId('lf-relance-confirmer'))
    await waitFor(() => expect(crmApi.initialiserRelance).toHaveBeenCalledTimes(2))
    expect(crmApi.initialiserRelance.mock.calls[1][1]).toEqual(CONTRAT.corps_devis_choisi)
    await waitFor(() => expect(toast.success).toHaveBeenCalledTimes(1))
    expect(ancien.id).not.toBe(recent.id)
  })

  it('un autre devis choisi part à sa place', async () => {
    const user = userEvent.setup()
    const question = CONTRAT.exemple_devis_a_choisir
    crmApi.initialiserRelance
      .mockImplementationOnce(() => refus(409, question))
      .mockImplementationOnce(() => Promise.resolve({ data: [] }))
    await relancerApresDevis(user)
    const ancien = question.devis_a_choisir.choix[1]
    await user.selectOptions(await screen.findByLabelText('Devis cité par le suivi'), String(ancien.id))
    await user.click(screen.getByTestId('lf-relance-confirmer'))
    await waitFor(() => expect(crmApi.initialiserRelance).toHaveBeenCalledTimes(2))
    expect(crmApi.initialiserRelance.mock.calls[1][1]).toEqual(
      { ...CONTRAT.corps_devis_choisi, devis: ancien.id })
  })

  it('aucun devis : l’avertissement est dit AVANT de lancer, « Lancer sans devis » est explicite', async () => {
    const user = userEvent.setup()
    crmApi.initialiserRelance
      .mockImplementationOnce(() => refus(409, CONTRAT.exemple_sans_devis))
      .mockImplementationOnce(() => Promise.resolve({ data: [{ id: 1, devis: null }] }))
    await relancerApresDevis(user)

    const avert = await screen.findByTestId('cad55-sans-devis')
    expect(avert.textContent).toBe(CONTRAT.exemple_sans_devis.erreurs.devis[0])
    expect(toast.success).not.toHaveBeenCalled()
    const bouton = screen.getByTestId('lf-relance-confirmer')
    expect(bouton.textContent).toBe('Lancer sans devis')
    await user.click(bouton)
    await waitFor(() => expect(crmApi.initialiserRelance).toHaveBeenCalledTimes(2))
    expect(crmApi.initialiserRelance.mock.calls[1][1]).toEqual(CONTRAT.corps_sans_devis)
  })

  it('un 400 « devis » s’affiche sous le choix du devis', async () => {
    const user = userEvent.setup()
    crmApi.initialiserRelance
      .mockImplementationOnce(() => refus(409, CONTRAT.exemple_devis_a_choisir))
      .mockImplementationOnce(() => refus(400, CONTRAT.exemple_erreur_devis))
    await relancerApresDevis(user)
    await user.click(await screen.findByTestId('lf-relance-confirmer'))
    const erreur = await screen.findByText(CONTRAT.exemple_erreur_devis.erreurs.devis[0])
    expect(erreur.closest('[role="alert"]')).not.toBeNull()
    expect(screen.getByLabelText('Devis cité par le suivi')).toHaveAttribute('aria-invalid', 'true')
    expect(toast.error).not.toHaveBeenCalled()
  })
})
