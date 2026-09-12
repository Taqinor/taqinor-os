import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
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

/* NTOBS7 — écran de téléchargement de l'export de réversibilité + historique
   (complète NTOBS6). */

vi.mock('../../api/parametresApi', () => ({
  default: {
    getHistoriqueExportReversibilite: vi.fn(),
    declencherExportReversibilite: vi.fn(),
  },
}))

import parametresApi from '../../api/parametresApi'
import ExportReversibilitePage from './ExportReversibilitePage'

describe('ExportReversibilitePage (NTOBS7)', () => {
  it('affiche un état vide propre sans export lancé', async () => {
    parametresApi.getHistoriqueExportReversibilite.mockResolvedValue({ data: [] })
    renderPage(<ExportReversibilitePage />)
    await waitFor(() =>
      expect(screen.getByText(/Aucun export lancé/)).toBeInTheDocument())
  })

  it('liste un export prêt avec un lien de téléchargement', async () => {
    parametresApi.getHistoriqueExportReversibilite.mockResolvedValue({
      data: [{
        id: 1, statut: 'pret', taille_octets: 2048, token: 'abc123',
        expire_le: '2026-07-01T00:00:00Z', created_at: '2026-06-24T00:00:00Z',
      }],
    })
    renderPage(<ExportReversibilitePage />)
    await waitFor(() => expect(screen.getByText('Prêt')).toBeInTheDocument())
    const lien = screen.getByRole('link', { name: /Télécharger/ })
    expect(lien).toHaveAttribute(
      'href', '/api/django/core/export-reversibilite/telecharger/abc123/')
  })

  it('un export en_cours ne montre pas de lien de téléchargement', async () => {
    parametresApi.getHistoriqueExportReversibilite.mockResolvedValue({
      data: [{
        id: 2, statut: 'en_cours', taille_octets: null, token: '',
        expire_le: null, created_at: '2026-06-24T00:00:00Z',
      }],
    })
    renderPage(<ExportReversibilitePage />)
    await waitFor(() => expect(screen.getByText('En cours')).toBeInTheDocument())
    expect(screen.queryByRole('link', { name: /Télécharger/ })).not.toBeInTheDocument()
  })

  it('confirme puis lance un export', async () => {
    const user = userEvent.setup()
    parametresApi.getHistoriqueExportReversibilite.mockResolvedValue({ data: [] })
    parametresApi.declencherExportReversibilite.mockResolvedValue({
      data: { id: 3, statut: 'en_cours' },
    })
    renderPage(<ExportReversibilitePage />)
    await waitFor(() =>
      expect(screen.getByText(/Aucun export lancé/)).toBeInTheDocument())

    await user.click(screen.getByRole('button', { name: /Exporter toutes mes données/ }))
    await waitFor(() =>
      expect(screen.getByText(/Lancer un export complet/)).toBeInTheDocument())

    await user.click(screen.getByRole('button', { name: /Lancer l'export/ }))
    await waitFor(() =>
      expect(parametresApi.declencherExportReversibilite).toHaveBeenCalled())
  })
})
