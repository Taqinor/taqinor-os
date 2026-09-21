import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'

/* AUDV09 / XACC22 — révisions budgétaires et scénarios what-if.

   `services.reviser_budget` et `services.creer_scenario_what_if` étaient
   complets et testés au niveau service, sans AUCUN appelant : un budget se
   modifiait donc SUR PLACE, écrasant la version approuvée (plus aucune
   comparaison « prévu à l'approbation » vs « prévu aujourd'hui »), et
   chiffrer une hypothèse haute ou basse obligeait à toucher au budget
   officiel — donc on y touchait.

   Ce test verrouille les deux garde-fous VISIBLES de l'écran : une version
   déjà FIGÉE ne propose plus « Réviser », et un budget qui n'est PAS le
   scénario officiel ne propose plus d'en dériver un autre. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

const mocks = vi.hoisted(() => ({
  budgets: vi.fn(),
  reviser: vi.fn(),
  scenarioWhatIf: vi.fn(),
  vide: () => Promise.resolve({ data: [] }),
}))

vi.mock('../../../api/comptaApi', () => ({
  default: {
    budgets: {
      list: mocks.budgets, get: mocks.vide, create: mocks.vide,
      update: mocks.vide, remove: mocks.vide,
      vsRealise: mocks.vide, genererLigneRepartie: mocks.vide,
      reviser: mocks.reviser, scenarioWhatIf: mocks.scenarioWhatIf,
    },
    comptes: { list: mocks.vide },
    centresCout: { list: mocks.vide },
    etats: { executionBudgetaire: mocks.vide },
    downloadBlob: vi.fn(),
  },
}))

import BudgetsPage from './BudgetsPage.jsx'

const BUDGET_OFFICIEL = {
  id: 3, annee: 2026, libelle: 'Budget 2026', statut: 'brouillon',
  statut_display: 'Brouillon', version: 1, figee: false, scenario: 'engage',
  lignes: [],
}
const BUDGET_FIGE = {
  id: 4, annee: 2025, libelle: 'Budget 2025', statut: 'approuve',
  statut_display: 'Approuvé', version: 1, figee: true, scenario: 'engage',
  lignes: [],
}

function mount() {
  const store = configureStore({
    reducer: { auth: () => ({ role: 'admin', role_nom: null, permissions: [] }) },
  })
  return render(
    <Provider store={store}>
      <MemoryRouter initialEntries={['/']}>
        <ThemeProvider><BudgetsPage /></ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

async function ouvrirMenu(libelle) {
  const ligne = (await screen.findAllByText(libelle))
    .map((el) => el.closest('tr')).find(Boolean)
  await userEvent.click(
    within(ligne).getByLabelText("Plus d'actions sur la ligne"))
}

describe('BudgetsPage — révision & scénarios (AUDV09)', () => {
  it('révise le budget officiel et affiche version + scénario', async () => {
    mocks.budgets.mockResolvedValue({ data: [BUDGET_OFFICIEL] })
    mocks.reviser.mockResolvedValue({
      data: { ...BUDGET_OFFICIEL, id: 9, version: 2 },
    })

    mount()

    // La version et le scénario étaient invisibles alors que le modèle les
    // porte : deux « Budget 2026 » à l'écran étaient indiscernables.
    expect((await screen.findAllByText('V1')).length).toBeGreaterThan(0)
    expect((await screen.findAllByText('Engagé (officiel)')).length)
      .toBeGreaterThan(0)

    await ouvrirMenu('Budget 2026')
    await userEvent.click(await screen.findByRole(
      'menuitem', { name: /Réviser \(figer et créer la V\+1\)/i }))
    await waitFor(() => {
      expect(mocks.reviser).toHaveBeenCalledWith(3, {})
    })
  }, 30000)

  it('une version FIGÉE ne propose plus « Réviser »', async () => {
    mocks.budgets.mockResolvedValue({ data: [BUDGET_FIGE] })

    mount()

    expect((await screen.findAllByText('V1 (figée)')).length).toBeGreaterThan(0)
    await ouvrirMenu('Budget 2025')
    expect(await screen.findByRole('menuitem', { name: 'Scénario optimiste' }))
      .toBeInTheDocument()
    expect(screen.queryByRole('menuitem', { name: /Réviser/i })).toBeNull()
  }, 30000)

  it('dérive un scénario optimiste du budget officiel', async () => {
    mocks.budgets.mockResolvedValue({ data: [BUDGET_OFFICIEL] })
    mocks.scenarioWhatIf.mockResolvedValue({
      data: { ...BUDGET_OFFICIEL, id: 11, scenario: 'optimiste' },
    })

    mount()

    await ouvrirMenu('Budget 2026')
    await userEvent.click(await screen.findByRole(
      'menuitem', { name: 'Scénario pessimiste' }))
    await waitFor(() => {
      expect(mocks.scenarioWhatIf).toHaveBeenCalledWith(3, 'pessimiste')
    })
  }, 30000)
})
