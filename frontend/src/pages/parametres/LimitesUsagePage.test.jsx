import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
  }
})

function renderPage(ui) {
  return render(<MemoryRouter><ThemeProvider>{ui}</ThemeProvider></MemoryRouter>)
}

/* NTOBS8 — page « Limites & usage » unifiée (lecture seule). */

vi.mock('../../api/parametresApi', () => ({
  default: { getUsageLimites: vi.fn() },
}))

import parametresApi from '../../api/parametresApi'
import LimitesUsagePage from './LimitesUsagePage'

describe('LimitesUsagePage (NTOBS8)', () => {
  it('affiche au moins 3 ressources avec compteur courant/limite', async () => {
    parametresApi.getUsageLimites.mockResolvedValueOnce({
      data: {
        ressources: [
          { nom: 'Stockage documentaire', utilise: 1024 * 1024, limite: 1024 * 1024 * 10, unite: 'octets' },
          { nom: 'Requêtes API (mois courant)', utilise: 40, limite: 1000, unite: 'requêtes' },
          { nom: 'Utilisateurs actifs', utilise: 3, limite: null, unite: 'comptes' },
        ],
      },
    })
    renderPage(<LimitesUsagePage />)
    await waitFor(() => expect(screen.getByText('Stockage documentaire')).toBeInTheDocument())
    expect(screen.getByText('Requêtes API (mois courant)')).toBeInTheDocument()
    expect(screen.getByText('Utilisateurs actifs')).toBeInTheDocument()
    expect(screen.getByText(/illimité/)).toBeInTheDocument()
  })

  it('affiche un badge "Proche du seuil" à 80% et au-delà', async () => {
    parametresApi.getUsageLimites.mockResolvedValueOnce({
      data: {
        ressources: [
          { nom: 'Stockage documentaire', utilise: 90, limite: 100, unite: 'octets' },
        ],
      },
    })
    renderPage(<LimitesUsagePage />)
    await waitFor(() => expect(screen.getByText('Proche du seuil')).toBeInTheDocument())
  })

  it('affiche un badge "Atteint" à 100%', async () => {
    parametresApi.getUsageLimites.mockResolvedValueOnce({
      data: {
        ressources: [
          { nom: 'Stockage documentaire', utilise: 100, limite: 100, unite: 'octets' },
        ],
      },
    })
    renderPage(<LimitesUsagePage />)
    await waitFor(() => expect(screen.getByText('Atteint')).toBeInTheDocument())
  })
})
