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

/* NTOBS11 — état des dépendances externes (mode dégradé documenté). */

vi.mock('../../api/coreApi', () => ({
  default: { degradedMode: { getStatus: vi.fn() } },
}))

import coreApi from '../../api/coreApi'
import EtatDependancesPage from './EtatDependancesPage'

describe('EtatDependancesPage (NTOBS11)', () => {
  it('affiche une dépendance en panne avec ses impacts', async () => {
    coreApi.degradedMode.getStatus.mockResolvedValueOnce({
      data: [
        {
          cle: 'storage', label: 'Stockage objet (MinIO)', statut: 'down',
          impactees: ['Téléversement de documents'], continuent: ['CRUD leads/devis'],
        },
      ],
    })
    renderPage(<EtatDependancesPage />)
    await waitFor(() => expect(screen.getByText('Stockage objet (MinIO)')).toBeInTheDocument())
    expect(screen.getByText('Panne')).toBeInTheDocument()
    expect(screen.getByText('Téléversement de documents')).toBeInTheDocument()
    expect(screen.getByText('CRUD leads/devis')).toBeInTheDocument()
  })

  it('affiche un statut opérationnel normalement', async () => {
    coreApi.degradedMode.getStatus.mockResolvedValueOnce({
      data: [
        { cle: 'db', label: 'Base de données (PostgreSQL)', statut: 'ok', impactees: [], continuent: [] },
      ],
    })
    renderPage(<EtatDependancesPage />)
    await waitFor(() => expect(screen.getByText('Opérationnel')).toBeInTheDocument())
  })
})
