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

/* WR7 — Le journal de nettoyages liste les nettoyages et affiche l'évaluation
   de salissure (chute PR + reco) depuis /cleanings/ et /configs/{id}/soiling/.
   Un seul système supervisé → auto-sélectionné. */

vi.mock('../../api/monitoringApi', () => ({
  default: {
    getConfigs: vi.fn(() => Promise.resolve({
      data: [{ id: 5, installation: 11, provider: 'noop', enabled: true }],
    })),
    getCleanings: vi.fn(() => Promise.resolve({
      data: [
        { id: 1, installation: 11, date: '2026-05-10', note: 'Nettoyage complet' },
      ],
    })),
    getSoiling: vi.fn(() => Promise.resolve({
      data: {
        installation: 11,
        current_pr_pct: '88.00',
        baseline_pr_pct: '96.00',
        estimated_soiling_loss_pct: '8.00',
        last_cleaning_date: '2026-05-10',
        days_since_cleaning: 53,
        recommend_cleaning: true,
        reasons: ['chute de PR significative'],
      },
    })),
    addCleaning: vi.fn(() => Promise.resolve({ data: {} })),
    deleteCleaning: vi.fn(() => Promise.resolve({})),
  },
}))

vi.mock('../../api/installationsApi', () => ({
  default: {
    getInstallations: vi.fn(() => Promise.resolve({
      data: [{ id: 11, reference: 'INST-2026-001', client_nom: 'Amrani' }],
    })),
  },
}))

import monitoringApi from '../../api/monitoringApi'
import CleaningsPage from './CleaningsPage'

describe('CleaningsPage (WR7 — nettoyages + salissure)', () => {
  it('auto-sélectionne le système et affiche salissure + journal', async () => {
    renderPage(<CleaningsPage />)

    await waitFor(() => expect(monitoringApi.getSoiling).toHaveBeenCalledWith('5'))

    // Carte d'évaluation de salissure (recommandation de nettoyage).
    expect(await screen.findByTestId('soiling-card')).toBeInTheDocument()
    expect(screen.getByText('Nettoyage recommandé')).toBeInTheDocument()

    // Le nettoyage listé apparaît (DataTable rend la ligne en double).
    expect(screen.getAllByText('Nettoyage complet').length).toBeGreaterThan(0)

    // Le journal a bien été demandé pour l'installation (pas la config).
    expect(monitoringApi.getCleanings).toHaveBeenCalledWith({ installation: 11 })
  })
})
