import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'

vi.mock('../../api/axios', () => ({ default: { get: vi.fn() } }))

import api from '../../api/axios'
import CreditKpiCards from './CreditKpiCards'

const FED = {
  count: 5,
  tuiles: [
    { id: 'ventes_ca', label: 'CA', valeur: 1000 },
    { id: 'credit_dso_pondere', label: 'DSO pondéré par le risque crédit', valeur: 42.5, unite: 'jours' },
    { id: 'credit_taux_derogations', label: 'Taux de dérogations approuvées (90 j)', valeur: 0.25 },
    { id: 'credit_score_a', label: 'Clients score A', valeur: 3, unite: 'clients' },
    { id: 'credit_score_b', label: 'Clients score B', valeur: 1, unite: 'clients' },
  ],
}

describe('CreditKpiCards (WIR144)', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('affiche les 3 KPI crédit fédérés (DSO, taux dérogations, répartition)', async () => {
    api.get.mockResolvedValueOnce({ data: FED })
    render(<CreditKpiCards />)
    expect(await screen.findByText('DSO pondéré par le risque crédit')).toBeInTheDocument()
    expect(screen.getByText('42.5 jours')).toBeInTheDocument()
    expect(screen.getByText('25 %')).toBeInTheDocument()
    expect(screen.getByText('Répartition par score')).toBeInTheDocument()
    // Consomme bien l'endpoint fédéré et filtre les tuiles credit_*.
    expect(api.get).toHaveBeenCalledWith('/reporting/reports/kpi-federes/')
    expect(screen.queryByText('CA')).not.toBeInTheDocument()
  })

  it('ne rend rien quand aucune tuile crédit n\'est disponible', async () => {
    api.get.mockResolvedValueOnce({ data: { count: 1, tuiles: [{ id: 'ventes_ca', label: 'CA', valeur: 1 }] } })
    const { container } = render(<CreditKpiCards />)
    await waitFor(() => expect(api.get).toHaveBeenCalled())
    expect(screen.queryByTestId('credit-kpi-federes')).not.toBeInTheDocument()
    expect(container).toBeEmptyDOMElement()
  })
})
