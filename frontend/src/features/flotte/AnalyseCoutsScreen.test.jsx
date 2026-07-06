import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* XFLT7/15/18 — écran « Analyse des coûts » (pivot, remplacement, budget vs
   réalisé). On vérifie que chaque onglet appelle le rapport correspondant et
   rend son contenu, sans réseau (client API mocké). */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

const rapportCouts = vi.fn(() => Promise.resolve({
  data: { pivot: [{ cle: 'v1', libelle: '12345-A-6', total: 3200 }], outliers: [] },
}))
const rapportRemplacement = vi.fn(() => Promise.resolve({
  data: { vehicules: [], a_remplacer: [], budget_annuel_estime: 0 },
}))
const rapportBudget = vi.fn(() => Promise.resolve({
  data: { annee: 2026, categories: [], total_budgete: 0, total_realise: 0 },
}))

vi.mock('../../api/flotteApi', () => ({
  default: {
    rapportCouts: (...args) => rapportCouts(...args),
    rapportRemplacement: (...args) => rapportRemplacement(...args),
    rapportBudget: (...args) => rapportBudget(...args),
  },
}))

import AnalyseCoutsScreen from './AnalyseCoutsScreen'

beforeEach(() => { vi.clearAllMocks() })

function withProviders(ui) {
  return render(
    <MemoryRouter>
      <ThemeProvider>{ui}</ThemeProvider>
    </MemoryRouter>,
  )
}

describe('AnalyseCoutsScreen', () => {
  it('charge le pivot des coûts par défaut (group_by=vehicule)', async () => {
    withProviders(<AnalyseCoutsScreen />)
    await waitFor(() => expect(rapportCouts).toHaveBeenCalledWith({ group_by: 'vehicule' }))
    // DataTable rend la table desktop ET les cartes mobiles dans le DOM (le
    // point de rupture est géré en CSS) : deux correspondances attendues.
    await waitFor(() => expect(screen.getAllByText('12345-A-6').length).toBeGreaterThan(0))
  })

  it('recharge le pivot quand on change le regroupement', async () => {
    const user = userEvent.setup()
    withProviders(<AnalyseCoutsScreen />)
    await waitFor(() => expect(rapportCouts).toHaveBeenCalledWith({ group_by: 'vehicule' }))

    await user.click(screen.getByRole('radio', { name: 'Catégorie' }))
    await waitFor(() => expect(rapportCouts).toHaveBeenCalledWith({ group_by: 'categorie' }))
  })

  it('appelle le rapport de remplacement sur l’onglet dédié', async () => {
    const user = userEvent.setup()
    withProviders(<AnalyseCoutsScreen />)
    await user.click(screen.getByRole('tab', { name: 'Remplacement' }))
    await waitFor(() => expect(rapportRemplacement).toHaveBeenCalled())
  })

  it('appelle le rapport budget sur l’onglet dédié', async () => {
    const user = userEvent.setup()
    withProviders(<AnalyseCoutsScreen />)
    await user.click(screen.getByRole('tab', { name: 'Budget vs réalisé' }))
    await waitFor(() => expect(rapportBudget).toHaveBeenCalledWith({ annee: expect.any(Number) }))
  })
})
