import { describe, it, expect, vi, beforeAll, onTestFinished } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

beforeAll(polyfillResizeObserver)

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

vi.mock('../../api/installationsApi', async () => (await import('./monitoring.testHelpers.js')).installationsApiAmrani())

// ADRG47 — droit d'écriture du monitoring (`sav_gerer`, palier sav) simulé :
// vrai = porteur (Technicien) ; faux = Commercial du registre (aucun code sav).
const droit = vi.hoisted(() => ({ ecrire: true }))
vi.mock('../../features/sav/useDroitMetier', () => ({ default: () => droit.ecrire }))

import monitoringApi from '../../api/monitoringApi'
import CleaningsPage from './CleaningsPage'
import { polyfillResizeObserver } from '../../test/selectNatif'

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
    expect(monitoringApi.getCleanings).toHaveBeenCalledWith(expect.objectContaining({ installation: 11 }))
  })

  it('ADRG47 — un Commercial ne voit ni Ajouter ni Supprimer', async () => {
    droit.ecrire = false
    onTestFinished(() => { droit.ecrire = true })
    renderPage(<CleaningsPage />)
    await waitFor(() => expect(screen.getAllByText('Nettoyage complet').length).toBeGreaterThan(0))
    expect(screen.queryByRole('button', { name: /Ajouter/ })).toBeNull()
    expect(screen.queryAllByLabelText('Supprimer')).toHaveLength(0)
  })

  it('ADRG47 — un porteur de sav_gerer voit Ajouter et Supprimer', async () => {
    renderPage(<CleaningsPage />)
    expect(await screen.findByRole('button', { name: /Ajouter/ })).toBeInTheDocument()
    await waitFor(() => expect(screen.queryAllByLabelText('Supprimer').length).toBeGreaterThan(0))
  })
})

describe('CleaningsPage — AERR129 relecture rejetée', () => {
  it('relecture rejetée : les nettoyages restent', async () => {
    monitoringApi.getCleanings.mockResolvedValueOnce({
      data: [
        { id: 1, installation: 11, date: '2026-05-10', note: 'Nettoyage complet' },
        { id: 2, installation: 11, date: '2026-06-10', note: 'Rinçage seul' },
      ],
    })
    renderPage(<CleaningsPage />)
    await waitFor(() => expect(screen.getAllByText('Rinçage seul').length).toBeGreaterThan(0))
    monitoringApi.getCleanings.mockRejectedValueOnce(new Error('503'))
    fireEvent.click(screen.getByRole('button', { name: /Ajouter/ }))
    await waitFor(() => expect(screen.getByText(/Liste pas à jour/)).toBeInTheDocument())
    expect(screen.getAllByText('Nettoyage complet').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Rinçage seul').length).toBeGreaterThan(0)
    expect(screen.getByRole('button', { name: 'Réessayer' })).toBeInTheDocument()
    expect(screen.queryByText('Aucun nettoyage')).toBeNull()
  })
})
