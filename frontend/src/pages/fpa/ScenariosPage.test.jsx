import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* WIR199 — ScenariosPage était structurellement vide : aucun scénario n'était
   CRÉABLE (createScenario), les lignes de delta n'étaient jamais visibles ni
   ajoutables (getLignesScenario/createLigneScenario), et le panneau de
   sensibilité (analyse_sensibilite) n'était rendu par aucun écran. */

const getCycles = vi.fn()
const getScenarios = vi.fn()
const createScenario = vi.fn()
const getLignesScenario = vi.fn()
const createLigneScenario = vi.fn()
const sensibilite = vi.fn()
const comparerScenarios = vi.fn()
const promouvoirScenario = vi.fn()

vi.mock('../../api/fpaApi', () => ({
  default: {
    getCycles: (...a) => getCycles(...a),
    getScenarios: (...a) => getScenarios(...a),
    createScenario: (...a) => createScenario(...a),
    getLignesScenario: (...a) => getLignesScenario(...a),
    createLigneScenario: (...a) => createLigneScenario(...a),
    sensibilite: (...a) => sensibilite(...a),
    comparerScenarios: (...a) => comparerScenarios(...a),
    promouvoirScenario: (...a) => promouvoirScenario(...a),
  },
}))

import ScenariosPage from './ScenariosPage'

beforeEach(() => {
  vi.clearAllMocks()
  getCycles.mockResolvedValue({ data: [{ id: 1, nom: 'Budget 2026' }] })
  getScenarios.mockResolvedValue({ data: [{ id: 5, nom: 'Scénario A', est_scenario_base: false }] })
  createScenario.mockResolvedValue({ data: { id: 6 } })
  getLignesScenario.mockResolvedValue({ data: [] })
  createLigneScenario.mockResolvedValue({ data: { id: 9 } })
  sensibilite.mockResolvedValue({ data: { variable: 'taux_conversion', points: [{ variation_pct: -20, revenu_total: '80000.00' }] } })
})

async function choisirCycle(user) {
  await screen.findByLabelText('Cycle budgétaire')
  await user.selectOptions(screen.getByLabelText('Cycle budgétaire'), '1')
}

describe('ScenariosPage (WIR199)', () => {
  it('crée un scénario via createScenario', async () => {
    const user = userEvent.setup()
    render(<ScenariosPage />)
    await choisirCycle(user)

    await user.type(screen.getByLabelText('Nom du nouveau scénario'), 'Scénario prudent')
    await user.click(screen.getByRole('button', { name: 'Créer le scénario' }))

    await waitFor(() => expect(createScenario).toHaveBeenCalledWith({ cycle: '1', nom: 'Scénario prudent' }))
  })

  it('ouvre les lignes de delta et en ajoute une', async () => {
    const user = userEvent.setup()
    render(<ScenariosPage />)
    await choisirCycle(user)
    await screen.findByText('Scénario A')

    await user.click(screen.getByRole('button', { name: 'Lignes de delta' }))
    await waitFor(() => expect(getLignesScenario).toHaveBeenCalledWith({ scenario: 5 }))

    await user.type(screen.getByLabelText('Delta pourcentage'), '-10')
    await user.type(screen.getByLabelText('Raison du delta'), 'Prudence marché')
    await user.click(screen.getByRole('button', { name: 'Ajouter la ligne' }))

    await waitFor(() => expect(createLigneScenario).toHaveBeenCalledWith(expect.objectContaining({
      scenario: 5, delta_pct: '-10', raison: 'Prudence marché',
    })))
  })

  it("lance l'analyse de sensibilité et affiche les points", async () => {
    const user = userEvent.setup()
    render(<ScenariosPage />)
    await choisirCycle(user)

    await user.click(screen.getByRole('button', { name: 'Analyser' }))

    await waitFor(() => expect(sensibilite).toHaveBeenCalledWith({ cycle: '1', variable: 'taux_conversion', plage: '20' }))
    expect(await screen.findByText('-20%')).toBeInTheDocument()
  })
})
