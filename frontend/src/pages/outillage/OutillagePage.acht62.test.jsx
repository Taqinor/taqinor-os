// ACHT62 — l'outillage lit TOUTES les pages (faux serveur DRF paginé à 50).
import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import { polyfillResizeObserver } from '../../test/selectNatif'

beforeAll(polyfillResizeObserver)

const PAGE_SIZE = 50
const OUTILS = Array.from({ length: 55 }, (_, i) => ({
  id: i + 1, nom: `Outil ${i}`, categorie: 'Mesure', asset_tag: `SONDE-${String(i).padStart(3, '0')}`,
  numero_serie: '', emplacement: null, emplacement_nom: null, statut: 'disponible',
  date_achat: null, note: '', intervalle_calibration_mois: 0, a_calibrer: false,
}))

vi.mock('../../api/outillageApi', () => ({
  default: {
    getOutils: ({ page = 1 } = {}) => {
      const debut = (page - 1) * 50
      return Promise.resolve({
        data: {
          count: 55,
          next: debut + 50 < 55 ? `?page=${page + 1}` : null,
          results: Array.from({ length: 55 }, (_, i) => ({
            id: i + 1, nom: `Outil ${i}`, categorie: 'Mesure', asset_tag: `SONDE-${String(i).padStart(3, '0')}`,
            numero_serie: '', emplacement: null, emplacement_nom: null, statut: 'disponible',
            date_achat: null, note: '', intervalle_calibration_mois: 0, a_calibrer: false,
          })).slice(debut, debut + 50),
        },
      })
    },
  },
}))
vi.mock('../../api/stockApi', () => ({
  default: { getEmplacements: () => Promise.resolve({ data: [] }) },
}))

import OutillagePage from './OutillagePage'

describe('OutillagePage — ACHT62 pages complètes', () => {
  it('trouve par la recherche un outil de la 2e page (SONDE-054)', async () => {
    expect(OUTILS).toHaveLength(55)
    expect(PAGE_SIZE).toBe(50)
    const user = userEvent.setup()
    render(
      <MemoryRouter><ThemeProvider><OutillagePage /></ThemeProvider></MemoryRouter>,
    )
    await waitFor(() => expect(screen.getByText('Outil 0')).toBeInTheDocument())
    await user.type(screen.getByPlaceholderText(/Rechercher/), 'SONDE-054')
    await waitFor(() => expect(screen.getByText('Outil 54')).toBeInTheDocument())
  })
})
