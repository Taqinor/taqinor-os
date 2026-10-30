import { describe, it, expect, vi, beforeAll, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { documentContrat } from '../../test/fixtures/contractSamples'
import { polyfillResizeObserver } from '../../test/selectNatif'

/* AANA45 / D-AANA-036-BRANCHER — bloc « Achats → paiement » (KPI P2P).
   La charge utile vient du contrat partagé `kpi_p2p.json` (PACT10), asserté
   côté serveur par `tests_ntp2p46_kpi.py` : aucun mock écrit à la main. */

vi.mock('../../api/reportingApi', () => ({
  default: { kpiP2p: vi.fn() },
}))

import reportingApi from '../../api/reportingApi'
import KpiP2pCard from './KpiP2pCard'

const CONTRAT = documentContrat('reporting', 'kpi_p2p').exemple

beforeAll(polyfillResizeObserver)
beforeEach(() => { reportingApi.kpiP2p.mockReset() })
afterEach(cleanup)

describe('KpiP2pCard (AANA45)', () => {
  it('affiche exactement les valeurs servies par le contrat', async () => {
    reportingApi.kpiP2p.mockResolvedValue({ data: CONTRAT })
    render(<KpiP2pCard />)

    expect(screen.getByTestId('kpi-p2p-chargement')).toBeInTheDocument()
    expect(await screen.findByText('Achats → paiement')).toBeInTheDocument()
    expect(await screen.findByText(/Délai demande → bon de commande/)).toBeInTheDocument()
    expect(screen.getByText(/3[,.]5\s*j/)).toBeInTheDocument()
    expect(screen.getByText(/70[,.]0/)).toBeInTheDocument()
    expect(screen.getByText(/75[,.]0\s*%/)).toBeInTheDocument()
    expect(screen.getByText('Période du 2026-10-01 au 2026-10-31')).toBeInTheDocument()

    const budget = CONTRAT.budgets_departement[0]
    const bloc = screen.getByTestId(`kpi-p2p-budget-${budget.budget_id}`)
    expect(within(bloc).getByText('Budget achats · octobre 2026')).toBeInTheDocument()
    expect(within(bloc).getByText(/42[,.]0\s*%\s*consommé/)).toBeInTheDocument()
    expect(within(bloc).getByText(/100\s?000\s*DH/)).toBeInTheDocument()
    expect(within(bloc).getByText(/58\s?000\s*DH/)).toBeInTheDocument()
    expect(reportingApi.kpiP2p).toHaveBeenCalledTimes(1)
  })

  it('omet une valeur null au lieu d’inventer un zéro', async () => {
    reportingApi.kpiP2p.mockResolvedValue({
      data: {
        ...CONTRAT,
        delai_demande_bcf_jours: null,
        conformite_fournisseur_moyenne: null,
        budgets_departement: [],
      },
    })
    render(<KpiP2pCard />)

    expect(await screen.findByText(/Demandes d’achat commandées/)).toBeInTheDocument()
    expect(screen.queryByText(/Délai demande/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Conformité fournisseurs/)).not.toBeInTheDocument()
    expect(screen.queryByTestId(/kpi-p2p-budget-/)).not.toBeInTheDocument()
  })

  it('dit l’état vide quand le serveur ne sert aucune valeur', async () => {
    reportingApi.kpiP2p.mockResolvedValue({
      data: {
        debut: null,
        fin: null,
        delai_demande_bcf_jours: null,
        budgets_departement: [],
        conformite_fournisseur_moyenne: null,
        taux_conversion_pct: null,
      },
    })
    render(<KpiP2pCard />)

    expect(await screen.findByTestId('kpi-p2p-vide')).toBeInTheDocument()
    expect(screen.queryByText(/Période du/)).not.toBeInTheDocument()
  })

  it('montre l’erreur et recharge au clic sur Réessayer', async () => {
    reportingApi.kpiP2p.mockRejectedValueOnce(new Error('boom'))
    reportingApi.kpiP2p.mockResolvedValueOnce({ data: CONTRAT })
    render(<KpiP2pCard />)

    expect(await screen.findByRole('alert')).toHaveTextContent('Impossible de charger les indicateurs achats.')
    await userEvent.click(screen.getByRole('button', { name: 'Réessayer' }))
    await waitFor(() => expect(reportingApi.kpiP2p).toHaveBeenCalledTimes(2))
    expect(await screen.findByText(/Délai demande → bon de commande/)).toBeInTheDocument()
  })
})
