import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* NTLOG24 — tableau de bord logistique : cartes KPI + répartition flotte
   propre/affrètement, sur `ordres-transport/tableau-bord-logistique/`. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

const { get } = vi.hoisted(() => ({ get: vi.fn() }))
vi.mock('../../api/axios', () => ({ default: { get } }))

import TableauBordLogistique from './TableauBordLogistique'

const DASHBOARD = {
  periode: null,
  nb_ordres: 2,
  nb_livres: 2,
  total_fret_ht: '300.00',
  poids_livre_kg: '1500.00',
  cout_par_kg_transporte: '0.2',
  taux_service_pct: 50.0,
  litiges_ouverts_count: 1,
  litiges_ouverts_montant_conteste: '400.00',
  repartition_mode_transport: { flotte_propre: 1, affretement: 1 },
  co2_total_estime_kg: '5.000',
}

function withProviders(ui) {
  return render(
    <MemoryRouter>
      <ThemeProvider>{ui}</ThemeProvider>
    </MemoryRouter>,
  )
}

describe('TableauBordLogistique', () => {
  it('charge le tableau de bord et affiche les cartes KPI', async () => {
    get.mockResolvedValueOnce({ data: DASHBOARD })
    withProviders(<TableauBordLogistique />)

    await waitFor(() => expect(get).toHaveBeenCalledWith(
      '/transport/ordres-transport/tableau-bord-logistique/', { params: {} },
    ))
    await screen.findByText('Coût / kg transporté')
    expect(screen.getByText('Litiges ouverts')).toBeInTheDocument()
    expect(screen.getByText('2 ordre(s) livré(s)')).toBeInTheDocument()
  })

  it('relance l’appel avec la période choisie', async () => {
    get.mockResolvedValue({ data: DASHBOARD })
    withProviders(<TableauBordLogistique />)
    await waitFor(() => expect(get).toHaveBeenCalled())

    const input = screen.getByLabelText('Période')
    input.value = '2026-04'
    input.dispatchEvent(new Event('input', { bubbles: true }))

    await waitFor(() => expect(get).toHaveBeenCalledWith(
      '/transport/ordres-transport/tableau-bord-logistique/',
      { params: { periode: '2026-04' } },
    ))
  })
})
