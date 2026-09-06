// MRY15 — remplace l'ancien « Initialiser le plan de relance » (fondation
// relance du 24/08/2026, revue Fable finale) : le moteur démarre maintenant
// SEUL à l'arrivée d'un lead vivant (MRY6). Ce contrôle sert désormais à
// RELANCER une cadence à la main (choix contact/après devis/réveil) ou à
// L'ARRÊTER (motif obligatoire). Couvre : appel de l'API, gestion du succès
// comme de l'échec via le toast maison (ui/confirm), jamais un throw non
// attrapé qui casserait l'écran.
import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { initState } from '../draftCore'
import SectionPipeline from './SectionPipeline'

vi.mock('../../../../api/crmApi', () => ({
  default: {
    initialiserRelance: vi.fn(),
    arreterCadence: vi.fn(),
    // MRY15 — CadenceFrise se charge elle-même au montage (mode édition).
    getRelanceEtapesLead: vi.fn(() => Promise.resolve({ data: { count: 0, results: [] } })),
    // useCanaux() (référentiel Canal géré) appelle getCanaux() au montage —
    // sans ce stub, chaque test crashe AVANT d'atteindre le bouton testé.
    getCanaux: vi.fn(() => Promise.resolve({ data: [] })),
  },
}))
// Même patron que DiffPlan.test.jsx : toastPromise ne fait que RENVOYER sa
// promesse (le vrai toast sonner n'est pas ce qu'on vérifie ici) ; on capture
// les messages passés pour prouver qu'ils restent en français et honnêtes
// sur le succès/l'échec — jamais la promesse « avalée » sans passer par lui.
const toastPromiseMock = vi.fn((p) => p)
vi.mock('../../../../ui/confirm', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
  toastPromise: (...args) => toastPromiseMock(...args),
}))

import crmApi from '../../../../api/crmApi'

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

const REF_DATA = { users: [], tagOptions: [], motifOptions: [] }

function renderSection(over = {}) {
  const state = initState({ lead: { id: 77, ...over }, mode: 'edit' })
  return render(
    <SectionPipeline state={state} setField={vi.fn()} errors={{}} refData={REF_DATA} />,
  )
}

describe('SectionPipeline — « Relancer / Arrêter la cadence » (MRY15)', () => {
  it('un lead existant (mode édition) affiche les contrôles, absents en création', () => {
    renderSection()
    expect(screen.getByTestId('lf-relance-cadence')).toBeTruthy()
    expect(screen.getByTestId('lf-arreter-cadence')).toBeTruthy()
    cleanup()

    const stateCreate = initState({ mode: 'create' })
    render(<SectionPipeline state={stateCreate} setField={vi.fn()} errors={{}} refData={REF_DATA} />)
    expect(screen.queryByTestId('lf-relance-cadence')).toBeNull()
    expect(screen.queryByTestId('lf-arreter-cadence')).toBeNull()
  })

  it('« Relancer la cadence » → crmApi.initialiserRelance(leadId, {cadence: "contact"}) puis toast de succès', async () => {
    const user = userEvent.setup()
    crmApi.initialiserRelance.mockResolvedValue({ data: [{ id: 1 }, { id: 2 }] })
    renderSection()

    await user.click(screen.getByTestId('lf-relance-cadence'))

    expect(crmApi.initialiserRelance).toHaveBeenCalledTimes(1)
    expect(crmApi.initialiserRelance).toHaveBeenCalledWith(77, { cadence: 'contact' })
    // La promesse de l'appel passe bien PAR toastPromise (jamais un
    // toast.success manuel à côté) — avec des messages FR honnêtes.
    await waitFor(() => expect(toastPromiseMock).toHaveBeenCalledTimes(1))
    const [, messages] = toastPromiseMock.mock.calls[0]
    expect(messages.success).toMatch(/relancée/i)
    expect(messages.error).toMatch(/impossible/i)
  })

  it('un échec serveur (403/500) sur « Relancer » ne casse pas l\'écran — le bouton redevient cliquable', async () => {
    const user = userEvent.setup()
    crmApi.initialiserRelance.mockRejectedValue({ response: { status: 403 } })
    renderSection()

    const bouton = screen.getByTestId('lf-relance-cadence')
    await user.click(bouton)

    await waitFor(() => expect(crmApi.initialiserRelance).toHaveBeenCalledTimes(1))
    // Pas d'exception non attrapée : le bouton reste dans le DOM, redevient actif.
    await waitFor(() => expect(screen.getByTestId('lf-relance-cadence')).not.toBeDisabled())
  })

  it('« Arrêter la cadence » exige un motif puis appelle crmApi.arreterCadence', async () => {
    const user = userEvent.setup()
    crmApi.arreterCadence.mockResolvedValue({ data: { arretees: 3 } })
    renderSection()

    await user.click(screen.getByTestId('lf-arreter-cadence'))
    const confirmer = screen.getByRole('button', { name: 'Confirmer' })
    // Motif vide : le bouton reste désactivé, aucun appel.
    expect(confirmer).toBeDisabled()

    await user.type(screen.getByTestId('lf-arreter-cadence-motif'), 'Client injoignable')
    await user.click(screen.getByRole('button', { name: 'Confirmer' }))

    expect(crmApi.arreterCadence).toHaveBeenCalledWith(77, { motif: 'Client injoignable' })
    await waitFor(() => expect(toastPromiseMock).toHaveBeenCalledTimes(1))
    const [, messages] = toastPromiseMock.mock.calls[0]
    expect(messages.success).toMatch(/arrêtée/i)
  })

  it('le bouton « Relancer » est désactivé pendant l\'appel en vol (anti double-clic)', async () => {
    const user = userEvent.setup()
    let resolvePromise
    crmApi.initialiserRelance.mockReturnValue(new Promise((resolve) => { resolvePromise = resolve }))
    renderSection()

    const bouton = screen.getByTestId('lf-relance-cadence')
    await user.click(bouton)
    await waitFor(() => expect(bouton).toBeDisabled())

    resolvePromise({ data: [] })
    await waitFor(() => expect(bouton).not.toBeDisabled())
  })
})
