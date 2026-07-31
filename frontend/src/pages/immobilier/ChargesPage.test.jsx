import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* WIR149 — saisie d'une dépense réelle de charges (`DepenseCharges`),
   jusqu'ici `ChargesPage.jsx` n'affichait que la consommation agrégée sans
   aucun moyen de créer une dépense depuis l'UI. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

const createDepense = vi.fn(() => Promise.resolve({ data: { id: 10 } }))
let totalReel = 1000

vi.mock('../../api/immobilierApi', () => ({
  default: {
    batiments: {
      list: vi.fn(() => Promise.resolve({ data: [{ id: 1, nom: 'Immeuble A' }] })),
      genererRegularisation: vi.fn(),
    },
    budgetsCharges: {
      list: vi.fn(() => Promise.resolve({
        data: [{ id: 7, poste: 'nettoyage', poste_display: 'Nettoyage', montant_budgete_annuel: '5000' }],
      })),
      consommation: vi.fn(() => Promise.resolve({
        data: { total_reel: totalReel, ecart_pct: -0.2 },
      })),
    },
    depensesCharges: {
      create: (...args) => createDepense(...args),
    },
    regularisationsCharges: { emettre: vi.fn() },
  },
}))

import ChargesPage from './ChargesPage'

beforeEach(() => {
  vi.clearAllMocks()
  totalReel = 1000
})

function withProviders(ui) {
  return render(
    <MemoryRouter>
      <ThemeProvider>{ui}</ThemeProvider>
    </MemoryRouter>,
  )
}

describe('ChargesPage — dépenses (WIR149)', () => {
  it('ajoute une dépense et recharge immédiatement le cumul réel', async () => {
    const user = userEvent.setup()
    withProviders(<ChargesPage />)

    await user.selectOptions(screen.getByLabelText('Sélectionner un bâtiment'), '1')
    await user.click(screen.getByRole('button', { name: 'Charger' }))
    await waitFor(() => expect(screen.getByText('Nettoyage')).toBeInTheDocument())

    await user.selectOptions(screen.getByLabelText('Poste'), '7')
    fireEvent.change(screen.getByLabelText('Date de la dépense'), { target: { value: '2026-07-15' } })
    await user.type(screen.getByLabelText('Montant réel'), '300')

    // Le second chargement (déclenché après création) doit refléter le
    // nouveau cumul réel dans le tableau, sans rechargement manuel.
    totalReel = 1300
    await user.click(screen.getByRole('button', { name: 'Ajouter la dépense' }))

    await waitFor(() => expect(createDepense).toHaveBeenCalledWith(
      expect.objectContaining({ budget_charges: 7, date: '2026-07-15', montant_reel: '300' }),
    ))
    await waitFor(() => expect(screen.getAllByText(/1\s?300|1300/).length).toBeGreaterThan(0))
  })
})
