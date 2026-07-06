import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* XFLT24/28 — écran Zones & rappels : évaluation du géofencing et
   rapprochement d'un rappel constructeur contre le parc de VIN. On vérifie
   l'appel exact au bon endpoint flotteApi, sans réseau. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

const evaluer = vi.fn(() => Promise.resolve({ data: { nb_alertes: 2, alertes: [] } }))
const rapprocher = vi.fn(() => Promise.resolve({ data: { nb_vin_matches: 3, signalements_crees: [1, 2, 3] } }))

vi.mock('../../api/flotteApi', () => ({
  default: {
    zonesGeographiques: {
      list: () => Promise.resolve({ data: [{ id: 1, nom: 'Dépôt Casablanca', type_zone_display: 'Dépôt', rayon_metres: 200, actif: true }] }),
      evaluer: (...args) => evaluer(...args),
    },
    rappelsConstructeur: {
      list: () => Promise.resolve({ data: [{ id: 5, reference_campagne: 'REC-2026-01', constructeur: 'Renault', vin_concernes: ['VIN1', 'VIN2'] }] }),
      rapprocher: (...args) => rapprocher(...args),
    },
  },
}))

import ZonesRappelsScreen from './ZonesRappelsScreen'

beforeEach(() => { vi.clearAllMocks() })

function withProviders(ui) {
  return render(
    <MemoryRouter>
      <ThemeProvider>{ui}</ThemeProvider>
    </MemoryRouter>,
  )
}

describe('ZonesRappelsScreen', () => {
  it('évalue le géofencing depuis l’onglet Zones', async () => {
    const user = userEvent.setup()
    withProviders(<ZonesRappelsScreen />)

    // DataTable rend la table desktop ET les cartes mobiles dans le DOM (le
    // point de rupture est géré en CSS) : deux correspondances attendues.
    await waitFor(() => expect(screen.getAllByText('Dépôt Casablanca').length).toBeGreaterThan(0))
    await user.click(screen.getByRole('button', { name: 'Évaluer le géofencing' }))
    await waitFor(() => expect(evaluer).toHaveBeenCalled())
  })

  it('rapproche un rappel constructeur contre le parc de VIN', async () => {
    const user = userEvent.setup()
    withProviders(<ZonesRappelsScreen />)

    await user.click(screen.getByRole('tab', { name: 'Rappels constructeur' }))
    await waitFor(() => expect(screen.getAllByText('REC-2026-01').length).toBeGreaterThan(0))
    await user.click(screen.getAllByRole('button', { name: 'Rapprocher contre le parc' })[0])
    await waitFor(() => expect(rapprocher).toHaveBeenCalledWith(5))
  })
})
