import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* ODY19 — Cockpit Après-vente : identité (ModuleHero) + actions rapides +
   bandeau KPI (réutilise savApi.getSavFileAction(), déjà mocké de la même
   façon que SavActionBoardPage.test.jsx). */

vi.mock('../../api/savApi', () => ({
  default: { getSavFileAction: vi.fn() },
}))

import savApi from '../../api/savApi'
import SavCockpitPage from './SavCockpitPage'

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('SavCockpitPage', () => {
  it('affiche l’identité, les KPI par bucket et les actions rapides', async () => {
    savApi.getSavFileAction.mockResolvedValue({
      data: {
        buckets: {
          a_repondre: { count: 2, ids: [1, 2] },
          a_planifier: { count: 1, ids: [3] },
          a_relancer: { count: 0, ids: [] },
          a_cloturer: { count: 1, ids: [4] },
          sans_action: { count: 5, ids: [] },
        },
      },
    })
    render(<MemoryRouter><SavCockpitPage /></MemoryRouter>)

    expect(await screen.findByRole('heading', { name: 'Après-vente' })).toBeInTheDocument()
    // 4 tickets répartis sur les buckets actionnables (2+1+0+1), sans_action exclu.
    expect(await screen.findByText(/4 tickets ouverts à traiter/)).toBeInTheDocument()
    expect(screen.getByText('À répondre')).toBeInTheDocument()
    expect(screen.getByText('À planifier')).toBeInTheDocument()
    expect(screen.getByText('À relancer')).toBeInTheDocument()
    expect(screen.getByText('À clôturer')).toBeInTheDocument()

    expect(screen.getByRole('link', { name: /Tickets SAV/ })).toHaveAttribute('href', '/sav')
    expect(screen.getByRole('link', { name: /Équipements/ })).toHaveAttribute('href', '/equipements')
    expect(screen.getByRole('link', { name: /Contrats maintenance/ })).toHaveAttribute('href', '/sav/contrats')
  })

  it('affiche un sous-titre neutre pendant le chargement', () => {
    savApi.getSavFileAction.mockReturnValue(new Promise(() => {})) // jamais résolu
    render(<MemoryRouter><SavCockpitPage /></MemoryRouter>)
    expect(screen.getByText('Tickets SAV, équipements et contrats de maintenance')).toBeInTheDocument()
  })
})
