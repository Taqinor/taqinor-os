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
const coutsCreate = vi.fn(() => Promise.resolve({ data: { id: 1 } }))
const budgetsCreate = vi.fn(() => Promise.resolve({ data: { id: 2 } }))

vi.mock('../../api/flotteApi', () => ({
  default: {
    rapportCouts: (...args) => rapportCouts(...args),
    rapportRemplacement: (...args) => rapportRemplacement(...args),
    rapportBudget: (...args) => rapportBudget(...args),
    actifs: { list: () => Promise.resolve({ data: [{ id: 1, label: '12345-A-6' }] }) },
    couts: { create: (...args) => coutsCreate(...args) },
    budgets: { create: (...args) => budgetsCreate(...args) },
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

  it('saisit un coût d’exploitation divers depuis le pivot (WIR46)', async () => {
    const user = userEvent.setup()
    withProviders(<AnalyseCoutsScreen />)
    await waitFor(() => expect(rapportCouts).toHaveBeenCalled())

    await user.click(await screen.findByRole('button', { name: 'Nouveau coût' }))
    await screen.findByRole('option', { name: '12345-A-6' })
    await user.selectOptions(screen.getByLabelText('Actif (véhicule ou engin)'), '1')
    await user.type(screen.getByLabelText('Date'), '2026-08-01')
    await user.type(screen.getByLabelText('Montant (MAD)'), '150')
    await user.click(screen.getByRole('button', { name: 'Créer' }))

    await waitFor(() => expect(coutsCreate).toHaveBeenCalledWith(
      expect.objectContaining({ actif_flotte: 1, categorie: 'peage', montant: 150 }),
    ))
  })

  it('saisit une ligne de budget flotte depuis l’onglet Budget (WIR46)', async () => {
    const user = userEvent.setup()
    withProviders(<AnalyseCoutsScreen />)
    await user.click(screen.getByRole('tab', { name: 'Budget vs réalisé' }))
    await waitFor(() => expect(rapportBudget).toHaveBeenCalled())

    await user.click(await screen.findByRole('button', { name: 'Nouveau budget' }))
    await user.type(screen.getByLabelText('Montant budgété (MAD)'), '50000')
    await user.click(screen.getByRole('button', { name: 'Créer' }))

    await waitFor(() => expect(budgetsCreate).toHaveBeenCalledWith(
      expect.objectContaining({ categorie: 'carburant', montant_budgete: 50000 }),
    ))
  })
})
