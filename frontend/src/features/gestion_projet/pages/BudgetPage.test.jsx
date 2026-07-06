import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import gestionProjetApi from '../../../api/gestionProjetApi'
import BudgetPage from './BudgetPage'

/* XPRJ14-17 — Prévision fin (ETC/EAC), burndown et points d'avancement (RAG)
   dans BudgetPage. Toutes les données sont INTERNES (jamais client). */

vi.mock('../../../api/gestionProjetApi', () => ({
  default: {
    getProjets: vi.fn(() => Promise.resolve({ data: [{ id: 10, code: 'P-1', nom: 'Villa Fès' }] })),
    getBudgets: vi.fn(() => Promise.resolve({ data: [] })),
    getLignesBudget: vi.fn(() => Promise.resolve({ data: [] })),
    getProjetCoutsEngagesReels: vi.fn(() => Promise.resolve({ data: null })),
    getPrevisionFin: vi.fn(() => Promise.resolve({
      data: {
        cpi: '0.95', budget_total: '100000', reel_total: '50000',
        etc_total: '55000', eac_total: '105000',
        ecart_eac_budget_total: '-5000', ecart_eac_budget_total_pct: '-5',
        par_categorie: [
          { categorie: 'materiel', budget: '60000', reel: '30000', etc: '32000', eac: '62000', ecart_eac_budget: '-2000', ecart_eac_budget_pct: '-3.3' },
        ],
      },
    })),
    getBurndown: vi.fn(() => Promise.resolve({
      data: {
        charge_totale: '100',
        points: [
          { date: '2026-07-01', charge_restante: '80', charge_ideale: '70', heures_loguees_cumulees: '20' },
          { date: '2026-07-08', charge_restante: '60', charge_ideale: '50', heures_loguees_cumulees: '40' },
        ],
      },
    })),
    getPointsAvancement: vi.fn(() => Promise.resolve({
      data: [{ id: 1, sante: 'orange', avancement_pct: 45, realisations: 'Pose toiture', risques: '', date_point: '2026-07-01' }],
    })),
    createPointAvancement: vi.fn(() => Promise.resolve({
      data: { id: 2, sante: 'vert', avancement_pct: '60', realisations: '', risques: '', date_point: '2026-07-06' },
    })),
  },
}))

vi.mock('../../../ui', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, toast: { success: vi.fn(), error: vi.fn() } }
})

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('BudgetPage', () => {
  it('affiche la prévision fin (ETC/EAC) et le point RAG après sélection du projet', async () => {
    const user = userEvent.setup()
    render(<BudgetPage />)
    await screen.findByRole('option', { name: /Villa Fès/ })
    await user.selectOptions(screen.getByLabelText('Projet'), '10')
    await waitFor(() => expect(gestionProjetApi.getPrevisionFin).toHaveBeenCalledWith(10))
    expect(await screen.findByText('Prévision fin de projet (ETC/EAC)')).toBeInTheDocument()
    expect(screen.getByText('Orange')).toBeInTheDocument()
    expect(screen.getByText('Pose toiture', { exact: false })).toBeInTheDocument()
  })

  it('crée un nouveau point d\'avancement via le formulaire', async () => {
    const user = userEvent.setup()
    render(<BudgetPage />)
    await screen.findByRole('option', { name: /Villa Fès/ })
    await user.selectOptions(screen.getByLabelText('Projet'), '10')
    await screen.findByText("Points d'avancement (RAG)")
    await user.click(screen.getByRole('button', { name: /Nouveau point/ }))
    await user.type(screen.getByLabelText('Avancement (%)'), '60')
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))
    await waitFor(() => expect(gestionProjetApi.createPointAvancement).toHaveBeenCalledWith(
      expect.objectContaining({ projet: '10', avancement_pct: '60' }),
    ))
  })
})
