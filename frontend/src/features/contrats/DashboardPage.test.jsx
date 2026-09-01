import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* NTSUB12/WIR252 — carte « Métriques SaaS » (ARR bridge, Quick Ratio, Rule of
   40) sur DashboardPage.jsx : le sélecteur pilotait déjà `getTableauBord`/
   `getMrrMouvements`/etc. sans jamais appeler `getMetriquesSaas` — resté
   API-only. Vérifie les 3 indicateurs, la tolérance `null` (division par
   zéro gardée côté serveur) et qu'une erreur 400 (ex. debut > fin) ne fait
   pas planter l'écran. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
  }
})

const { getMetriquesSaas } = vi.hoisted(() => ({
  getMetriquesSaas: vi.fn(() => Promise.resolve({ data: {
    arr_bridge: {
      arr_debut: '100000.00', new: '5000.00', expansion: '2000.00',
      contraction: '-1000.00', churn: '-500.00', arr_fin: '105500.00',
    },
    quick_ratio: '4.67',
    rule_of_40: { croissance_arr_pct: '5.50', marge_pct: '30.00', rule_of_40: '35.50' },
  } })),
}))

vi.mock('../../api/contratsApi', () => ({
  default: {
    getTableauBord: () => Promise.resolve({ data: {
      total: 12, actifs: 10, a_renouveler: 2, valeur_active: '500000.00',
      valeur_totale: '600000.00', mrr: '40000.00', mrr_combine: '42000.00',
    } }),
    getMrrMouvements: () => Promise.resolve({ data: {
      new: '5000', expansion: '2000', contraction: '-1000', churn: '-500', net: '5500',
    } }),
    getExceptionsFacturation: () => Promise.resolve({ data: [] }),
    getCohortesRetention: () => Promise.resolve({ data: { cohortes: {} } }),
    getMetriquesSaas,
  },
}))

import DashboardPage from './DashboardPage'

beforeEach(() => { vi.clearAllMocks() })

function renderPage() {
  return render(<MemoryRouter><ThemeProvider><DashboardPage /></ThemeProvider></MemoryRouter>)
}

describe('DashboardPage — Métriques SaaS (NTSUB12/WIR252)', () => {
  it('affiche les 3 indicateurs (ARR, Quick Ratio, Rule of 40)', async () => {
    getMetriquesSaas.mockResolvedValueOnce({ data: {
      arr_bridge: {
        arr_debut: '100000.00', new: '5000.00', expansion: '2000.00',
        contraction: '-1000.00', churn: '-500.00', arr_fin: '105500.00',
      },
      quick_ratio: '4.67',
      rule_of_40: { croissance_arr_pct: '5.50', marge_pct: '30.00', rule_of_40: '35.50' },
    } })
    renderPage()

    await waitFor(() => expect(getMetriquesSaas).toHaveBeenCalledWith({}))
    expect(await screen.findByText('Métriques SaaS (investisseur)')).toBeInTheDocument()
    expect(screen.getByText('ARR (fin de période)')).toBeInTheDocument()
    expect(screen.getByText('Quick Ratio')).toBeInTheDocument()
    expect(screen.getByText('4.67')).toBeInTheDocument()
    expect(screen.getByText('Rule of 40')).toBeInTheDocument()
    expect(screen.getByText('35.50')).toBeInTheDocument()
  })

  it('tolère un quick_ratio (et un rule_of_40) null — affiché « — », jamais recalculé', async () => {
    getMetriquesSaas.mockResolvedValueOnce({ data: {
      arr_bridge: {
        arr_debut: '100000.00', new: '0.00', expansion: '0.00',
        contraction: '0.00', churn: '0.00', arr_fin: '100000.00',
      },
      quick_ratio: null,
      rule_of_40: { croissance_arr_pct: null, marge_pct: null, rule_of_40: null },
    } })
    renderPage()

    await screen.findByText('Métriques SaaS (investisseur)')
    await waitFor(() => expect(getMetriquesSaas).toHaveBeenCalled())
    // Quick Ratio et Rule of 40 rendus « — » (jamais 0 ni une valeur inventée).
    // Aucune autre carte du tableau de bord n'affiche « — » avec ces mocks
    // (MRR/exceptions/cohortes ont toutes des données ou un message dédié).
    expect(screen.getAllByText('—').length).toBeGreaterThanOrEqual(2)
  })

  it('affiche une erreur 400 (debut > fin) sans planter l’écran', async () => {
    getMetriquesSaas.mockRejectedValueOnce({
      response: { status: 400, data: { detail: 'debut doit précéder fin.' } },
    })
    renderPage()

    expect(await screen.findByRole('alert')).toHaveTextContent('debut doit précéder fin.')
    // Le reste du tableau de bord reste rendu (pas de crash global).
    expect(screen.getByText('Tableau de bord des contrats')).toBeInTheDocument()
  })

  it('recharge avec la période choisie', async () => {
    renderPage()
    await waitFor(() => expect(getMetriquesSaas).toHaveBeenCalledWith({}))

    // Le bouton « Calculer » existe AUSSI sur la carte CLV (ClvCard) : on
    // scope explicitement au formulaire de la carte Métriques SaaS (repéré
    // par son champ « Début ») pour ne jamais matcher les deux.
    const debutInput = screen.getByLabelText('Début')
    const form = debutInput.closest('form')
    fireEvent.change(debutInput, { target: { value: '2026-01-01' } })
    fireEvent.change(within(form).getByLabelText('Fin'), { target: { value: '2026-06-30' } })
    await userEvent.click(within(form).getByRole('button', { name: /^Calculer$/i }))

    await waitFor(() => expect(getMetriquesSaas).toHaveBeenLastCalledWith({
      debut: '2026-01-01', fin: '2026-06-30',
    }))
  })
})
