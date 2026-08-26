// Revue Fable finale — le plan de relance structuré (crm.RelanceEtape,
// panneau « Relances du jour » du cockpit) n'avait AUCUN déclencheur côté
// UI : crmApi.initialiserRelance n'était jamais appelé nulle part, donc le
// widget restait vide en permanence quel que soit l'effort backend investi.
// Ce test couvre le bouton minimal ajouté ici (« Initialiser le plan de
// relance », près de « Relance le ») : appel de l'API, et gestion du succès
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

describe('SectionPipeline — « Initialiser le plan de relance » (fondation relance sans déclencheur)', () => {
  it('un lead existant (mode édition) affiche le bouton, absent en création', () => {
    renderSection()
    expect(screen.getByTestId('lf-init-relance')).toBeTruthy()
    cleanup()

    const stateCreate = initState({ mode: 'create' })
    render(<SectionPipeline state={stateCreate} setField={vi.fn()} errors={{}} refData={REF_DATA} />)
    expect(screen.queryByTestId('lf-init-relance')).toBeNull()
  })

  it('clic → crmApi.initialiserRelance(leadId) puis toast de succès (200)', async () => {
    const user = userEvent.setup()
    crmApi.initialiserRelance.mockResolvedValue({ data: [{ id: 1 }, { id: 2 }] })
    renderSection()

    await user.click(screen.getByTestId('lf-init-relance'))

    expect(crmApi.initialiserRelance).toHaveBeenCalledTimes(1)
    expect(crmApi.initialiserRelance).toHaveBeenCalledWith(77)
    // La promesse de l'appel passe bien PAR toastPromise (jamais un
    // toast.success manuel à côté) — avec des messages FR honnêtes.
    await waitFor(() => expect(toastPromiseMock).toHaveBeenCalledTimes(1))
    const [, messages] = toastPromiseMock.mock.calls[0]
    expect(messages.success).toMatch(/initialisé/i)
    expect(messages.error).toMatch(/impossible/i)
  })

  it('un échec serveur (403/500) ne casse pas l\'écran — le bouton redevient cliquable', async () => {
    const user = userEvent.setup()
    crmApi.initialiserRelance.mockRejectedValue({ response: { status: 403 } })
    renderSection()

    const bouton = screen.getByTestId('lf-init-relance')
    await user.click(bouton)

    await waitFor(() => expect(crmApi.initialiserRelance).toHaveBeenCalledTimes(1))
    // Pas d'exception non attrapée : le bouton reste dans le DOM, redevient actif.
    await waitFor(() => expect(screen.getByTestId('lf-init-relance')).not.toBeDisabled())
  })

  it('le bouton est désactivé pendant l\'appel en vol (anti double-clic)', async () => {
    const user = userEvent.setup()
    let resolvePromise
    crmApi.initialiserRelance.mockReturnValue(new Promise((resolve) => { resolvePromise = resolve }))
    renderSection()

    const bouton = screen.getByTestId('lf-init-relance')
    await user.click(bouton)
    await waitFor(() => expect(bouton).toBeDisabled())

    resolvePromise({ data: [] })
    await waitFor(() => expect(bouton).not.toBeDisabled())
  })
})
