import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* WIR199 — le module FP&A était structurellement inamorçable : aucun
   scénario créable (`fpaApi.createScenario` sans appelant), les deltas
   (`LigneScenario`) sans liste ni formulaire, et le panneau de sensibilité
   (NTFPA18) absent de l'écran. On verrouille les 3 nouveaux flux ici. */

const getCycles = vi.fn()
const getScenarios = vi.fn()
const createScenario = vi.fn()
const getLignesScenario = vi.fn()
const createLigneScenario = vi.fn()
const sensibilite = vi.fn()

vi.mock('../../api/fpaApi', () => ({
  default: {
    getCycles: (...a) => getCycles(...a),
    getScenarios: (...a) => getScenarios(...a),
    createScenario: (...a) => createScenario(...a),
    comparerScenarios: vi.fn(),
    promouvoirScenario: vi.fn(),
    getLignesScenario: (...a) => getLignesScenario(...a),
    createLigneScenario: (...a) => createLigneScenario(...a),
    sensibilite: (...a) => sensibilite(...a),
  },
}))

const toastSuccess = vi.fn()
const toastError = vi.fn()
vi.mock('../../ui', async (orig) => ({
  ...(await orig()),
  toast: { success: (...a) => toastSuccess(...a), error: (...a) => toastError(...a) },
}))

import ScenariosPage from './ScenariosPage'

function monter() {
  return render(
    <MemoryRouter>
      <ThemeProvider><ScenariosPage /></ThemeProvider>
    </MemoryRouter>,
  )
}

const CYCLES = [{ id: 1, nom: 'Budget 2027' }]
const SCENARIOS = [{ id: 5, nom: 'Optimiste', est_scenario_base: false }]

beforeEach(() => {
  vi.clearAllMocks()
  getCycles.mockResolvedValue({ data: CYCLES })
  getScenarios.mockResolvedValue({ data: SCENARIOS })
  createScenario.mockResolvedValue({ data: { id: 6 } })
  getLignesScenario.mockResolvedValue({ data: [] })
  createLigneScenario.mockResolvedValue({ data: { id: 10 } })
  sensibilite.mockResolvedValue({
    data: { variable: 'taux_conversion', points: [{ variation_pct: -20, revenu_total: '80000.00' }, { variation_pct: 0, revenu_total: '100000.00' }] },
  })
})

async function selectionnerCycle(user) {
  await user.selectOptions(screen.getByLabelText('Cycle budgétaire'), '1')
  await waitFor(() => expect(getScenarios).toHaveBeenCalledWith({ cycle: '1' }))
}

describe('ScenariosPage — création de scénario (WIR199)', () => {
  it('crée un scénario rattaché au cycle sélectionné', async () => {
    const user = userEvent.setup()
    monter()
    await waitFor(() => expect(getCycles).toHaveBeenCalled())
    await selectionnerCycle(user)

    await user.type(screen.getByLabelText('Nom du scénario'), 'Pessimiste')
    await user.click(screen.getByRole('button', { name: 'Créer le scénario' }))

    await waitFor(() => expect(createScenario).toHaveBeenCalledWith({
      cycle: '1', nom: 'Pessimiste', description: '',
    }))
    expect(toastSuccess).toHaveBeenCalledWith('Scénario créé.')
  })

  it('désactive la création sans nom', async () => {
    const user = userEvent.setup()
    monter()
    await waitFor(() => expect(getCycles).toHaveBeenCalled())
    await selectionnerCycle(user)
    expect(screen.getByRole('button', { name: 'Créer le scénario' })).toBeDisabled()
  })
})

describe('ScenariosPage — lignes de delta (WIR199)', () => {
  it('ouvre les lignes d’un scénario et en ajoute une', async () => {
    const user = userEvent.setup()
    monter()
    await waitFor(() => expect(getCycles).toHaveBeenCalled())
    await selectionnerCycle(user)

    await user.click(screen.getByRole('button', { name: 'Lignes de delta' }))
    await waitFor(() => expect(getLignesScenario).toHaveBeenCalledWith({ scenario: 5 }))

    await user.selectOptions(screen.getByLabelText('Catégorie du delta'), 'marketing')
    await user.type(screen.getByLabelText('Delta en pourcentage'), '-10')
    await user.click(screen.getByRole('button', { name: 'Ajouter la ligne' }))

    await waitFor(() => expect(createLigneScenario).toHaveBeenCalledWith({
      scenario: 5, categorie: 'marketing', delta_pct: '-10', delta_montant: null, raison: '',
    }))
    expect(toastSuccess).toHaveBeenCalledWith('Ligne de delta ajoutée.')
  })

  it('refuse une ligne sans catégorie ni delta', async () => {
    const user = userEvent.setup()
    monter()
    await waitFor(() => expect(getCycles).toHaveBeenCalled())
    await selectionnerCycle(user)
    await user.click(screen.getByRole('button', { name: 'Lignes de delta' }))
    await waitFor(() => expect(getLignesScenario).toHaveBeenCalled())

    await user.click(screen.getByRole('button', { name: 'Ajouter la ligne' }))

    expect(createLigneScenario).not.toHaveBeenCalled()
    expect(toastError).toHaveBeenCalledWith('Renseignez au moins une catégorie ou un delta.')
  })
})

describe('ScenariosPage — panneau de sensibilité (WIR199/NTFPA18)', () => {
  it('calcule et affiche les points de sensibilité', async () => {
    const user = userEvent.setup()
    monter()
    await waitFor(() => expect(getCycles).toHaveBeenCalled())
    await selectionnerCycle(user)

    await user.click(screen.getByRole('button', { name: 'Calculer' }))

    await waitFor(() => expect(sensibilite).toHaveBeenCalledWith({
      cycle: '1', variable: 'taux_conversion', plage: 20,
    }))
    expect(await screen.findByText('-20%')).toBeInTheDocument()
  })
})
