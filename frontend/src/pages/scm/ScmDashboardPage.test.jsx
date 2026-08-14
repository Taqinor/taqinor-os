import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* NTSCM28 — Tableau de bord SCM exécutif : affiche les 4 KPI de synthèse
   (taux de service, OTIF pondéré, MAPE global, valeur de stock par classe
   ABC), aucun prix d'achat en clair. */

const { apiMock } = vi.hoisted(() => ({ apiMock: { get: vi.fn() } }))
vi.mock('../../api/axios', () => ({ default: apiMock }))

import ScmDashboardPage from './ScmDashboardPage.jsx'

afterEach(() => {
  cleanup()
  apiMock.get.mockReset()
})

function mount() {
  return render(
    <MemoryRouter initialEntries={['/scm/dashboard']}>
      <ScmDashboardPage />
    </MemoryRouter>,
  )
}

describe('ScmDashboardPage (NTSCM28)', () => {
  it('affiche les 4 KPI', async () => {
    apiMock.get.mockResolvedValue({
      data: {
        taux_service_pct: 82.5,
        otif_pondere_pct: 91.2,
        mape_global_pct: 12.4,
        valeur_stock_par_classe_abc: {
          A: '60000.00', B: '10000.00', C: '2000.00',
        },
      },
    })
    mount()

    expect(await screen.findByText('Tableau de bord SCM exécutif')).toBeInTheDocument()
    expect(await screen.findByText('82.5%')).toBeInTheDocument()
    expect(screen.getByText('91.2%')).toBeInTheDocument()
    expect(screen.getByText('12.4%')).toBeInTheDocument()
  })

  it("affiche une erreur claire si l'accès est refusé", async () => {
    apiMock.get.mockRejectedValue({ response: { status: 403 } })
    mount()
    expect(await screen.findByText(/Réservé aux responsables et administrateurs/i))
      .toBeInTheDocument()
  })
})
