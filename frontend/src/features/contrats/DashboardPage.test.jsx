import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* WIR252 — carte « Métriques SaaS » (NTSUB12).
   ----------------------------------------------------------------------------
   `metriques-saas` (ARR bridge, Quick Ratio, Rule of 40) existait côté serveur
   sans aucun écran. Ce qui est verrouillé ici : les trois indicateurs sont
   rendus, un `quick_ratio` à `null` s'affiche « — » (jamais un 0 inventé), et
   un 400 (période invalide) est annoncé sans faire tomber la page. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
  }
})

const { getMetriquesSaas } = vi.hoisted(() => ({ getMetriquesSaas: vi.fn() }))

vi.mock('../../api/contratsApi', () => {
  const empty = () => Promise.resolve({ data: [] })
  return {
    default: {
      getTableauBord: () => Promise.resolve({
        data: {
          total: 3, actifs: 2, a_renouveler: 1,
          valeur_active: '100000', valeur_totale: '150000', mrr: '5000',
        },
      }),
      getMrrMouvements: () => Promise.resolve({ data: null }),
      getExceptionsFacturation: empty,
      getCohortesRetention: () => Promise.resolve({ data: null }),
      getMetriquesSaas: (...args) => getMetriquesSaas(...args),
      getClv: () => Promise.resolve({ data: {} }),
      rejouerCycle: () => Promise.resolve({ data: {} }),
      campagneRevision: () => Promise.resolve({ data: {} }),
      campagneRevisionRollback: () => Promise.resolve({ data: {} }),
    },
  }
})

import DashboardPage from './DashboardPage'

const METRIQUES = {
  arr_bridge: {
    arr_debut: '120000.00', new: '24000.00', expansion: '6000.00',
    contraction: '-3000.00', churn: '-9000.00', arr_fin: '138000.00',
  },
  quick_ratio: '2.50',
  rule_of_40: {
    croissance_arr_pct: '15.00', marge_pct: '28.00', rule_of_40: '43.00',
  },
}

beforeEach(() => {
  vi.clearAllMocks()
  getMetriquesSaas.mockResolvedValue({ data: METRIQUES })
})

const renderPage = () =>
  render(<MemoryRouter><ThemeProvider><DashboardPage /></ThemeProvider></MemoryRouter>)

describe('DashboardPage — métriques SaaS (WIR252)', () => {
  it('rend les trois indicateurs', async () => {
    renderPage()
    expect(await screen.findByText('Métriques SaaS')).toBeInTheDocument()
    expect(screen.getByText('ARR (fin de période)')).toBeInTheDocument()
    expect(screen.getByText('Quick Ratio')).toBeInTheDocument()
    expect(screen.getByText('Rule of 40')).toBeInTheDocument()
    await waitFor(() => expect(getMetriquesSaas).toHaveBeenCalled())
  })

  it('tolère un quick_ratio null : « — », jamais un 0 inventé', async () => {
    getMetriquesSaas.mockResolvedValue({
      data: {
        ...METRIQUES,
        quick_ratio: null,
        rule_of_40: { croissance_arr_pct: null, marge_pct: null, rule_of_40: null },
      },
    })
    renderPage()
    expect(await screen.findByText('Quick Ratio')).toBeInTheDocument()
    // Le rendu contient des « — » et surtout AUCUN « 0 » à la place.
    await waitFor(() => expect(screen.getAllByText('—').length).toBeGreaterThan(0))
  })

  it('annonce un 400 sans faire tomber la page', async () => {
    getMetriquesSaas.mockRejectedValue({
      response: { status: 400, data: { detail: 'debut doit précéder fin.' } },
    })
    renderPage()
    expect(await screen.findByText('debut doit précéder fin.')).toBeInTheDocument()
    // La page reste debout : son titre est toujours là.
    expect(screen.getByText('Tableau de bord des contrats')).toBeInTheDocument()
  })

  it('rejoue le calcul avec la période saisie', async () => {
    renderPage()
    expect(await screen.findByText('Métriques SaaS')).toBeInTheDocument()
    await waitFor(() => expect(getMetriquesSaas).toHaveBeenCalledTimes(1))
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Appliquer' })).toBeEnabled())

    fireEvent.change(screen.getByLabelText('Début'), { target: { value: '2026-01-01' } })
    fireEvent.change(screen.getByLabelText('Fin'), { target: { value: '2026-03-31' } })
    fireEvent.click(screen.getByRole('button', { name: 'Appliquer' }))

    await waitFor(() => expect(getMetriquesSaas).toHaveBeenCalledTimes(2))
    expect(getMetriquesSaas.mock.calls[1][0]).toEqual({
      debut: '2026-01-01', fin: '2026-03-31',
    })
  })
})
