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

/* NTOBS5 — écran self-service « Sauvegardes » : lecture seule des BackupRun
   déjà produits (YOPSB1/2). Alerte visuelle si le drill est périmé (>30j). */

vi.mock('../../api/parametresApi', () => ({
  default: {
    getMesSauvegardes: vi.fn(),
  },
}))

import parametresApi from '../../api/parametresApi'
import SauvegardesPage from './SauvegardesPage'

describe('SauvegardesPage (NTOBS5)', () => {
  it('affiche la dernière sauvegarde et un drill récent sans alerte de péremption', async () => {
    const hier = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString()
    parametresApi.getMesSauvegardes.mockResolvedValueOnce({
      data: {
        derniere_sauvegarde: { date: hier, statut: 'termine' },
        dernier_drill: { date: hier, statut: 'termine' },
        rpo_planifie: 'quotidien, 03:00',
        rto_annonce_heures: 24,
      },
    })
    renderPage(<SauvegardesPage />)
    await waitFor(() => expect(screen.getByText(/Réussie le/)).toBeInTheDocument())
    expect(screen.getByText(/quotidien, 03:00/)).toBeInTheDocument()
    expect(screen.queryByText(/Périmé/)).not.toBeInTheDocument()
  })

  it('affiche une alerte rouge si le drill est périmé (>30j sans succès)', async () => {
    const ancien = new Date(Date.now() - 45 * 24 * 60 * 60 * 1000).toISOString()
    parametresApi.getMesSauvegardes.mockResolvedValueOnce({
      data: {
        derniere_sauvegarde: { date: ancien, statut: 'termine' },
        dernier_drill: { date: ancien, statut: 'termine' },
        rpo_planifie: 'quotidien, 03:00',
        rto_annonce_heures: null,
      },
    })
    renderPage(<SauvegardesPage />)
    await waitFor(() => expect(screen.getByText(/Périmé/)).toBeInTheDocument())
  })

  it("affiche un état vide propre quand aucune sauvegarde n'existe encore", async () => {
    parametresApi.getMesSauvegardes.mockResolvedValueOnce({
      data: {
        derniere_sauvegarde: null,
        dernier_drill: null,
        rpo_planifie: null,
        rto_annonce_heures: null,
      },
    })
    renderPage(<SauvegardesPage />)
    await waitFor(() =>
      expect(screen.getByText(/Aucune sauvegarde réussie/)).toBeInTheDocument())
    expect(screen.getByText(/Aucun test de restauration/)).toBeInTheDocument()
  })
})
