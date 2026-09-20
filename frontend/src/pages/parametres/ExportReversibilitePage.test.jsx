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

vi.mock('../../api/coreApi', () => ({
  default: {
    datasetsExplorateur: { list: vi.fn() },
  },
}))

import parametresApi from '../../api/parametresApi'
import coreApi from '../../api/coreApi'
import ExportReversibilitePage from './ExportReversibilitePage'

const DATASETS = [
  { name: 'crm_leads', label: 'Leads CRM' },
  { name: 'ventes_devis', label: 'Devis' },
  { name: 'sav_tickets', label: 'Tickets SAV' },
]

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

  it('assistant 2 étapes : tout coché par défaut → lance sans restreindre les datasets', async () => {
    const user = userEvent.setup()
    parametresApi.getHistoriqueExportReversibilite.mockResolvedValue({ data: [] })
    parametresApi.declencherExportReversibilite.mockResolvedValue({
      data: { id: 3, statut: 'en_cours' },
    })
    coreApi.datasetsExplorateur.list.mockResolvedValue({ data: DATASETS })
    renderPage(<ExportReversibilitePage />)
    await waitFor(() =>
      expect(screen.getByText(/Aucun export lancé/)).toBeInTheDocument())

    await user.click(screen.getByRole('button', { name: /Exporter toutes mes données/ }))
    await waitFor(() =>
      expect(screen.getByText(/étape 1\/2/)).toBeInTheDocument())
    expect(await screen.findByText('Leads CRM')).toBeInTheDocument()
    // Tout coché par défaut.
    for (const cb of screen.getAllByRole('checkbox')) expect(cb).toBeChecked()

    await user.click(screen.getByRole('button', { name: 'Suivant' }))
    await waitFor(() => expect(screen.getByText(/étape 2\/2/)).toBeInTheDocument())
    expect(screen.getByText(/3 jeux de données sélectionnés sur 3/)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /Lancer l'export/ }))
    await waitFor(() =>
      // Tout sélectionné → payload `undefined` (comportement par défaut inchangé).
      expect(parametresApi.declencherExportReversibilite).toHaveBeenCalledWith(undefined))
  })

  it('décocher un jeu de données le retire du payload envoyé au serveur', async () => {
    const user = userEvent.setup()
    parametresApi.getHistoriqueExportReversibilite.mockResolvedValue({ data: [] })
    parametresApi.declencherExportReversibilite.mockResolvedValue({
      data: { id: 4, statut: 'en_cours' },
    })
    coreApi.datasetsExplorateur.list.mockResolvedValue({ data: DATASETS })
    renderPage(<ExportReversibilitePage />)
    await waitFor(() =>
      expect(screen.getByText(/Aucun export lancé/)).toBeInTheDocument())

    await user.click(screen.getByRole('button', { name: /Exporter toutes mes données/ }))
    const ticketsCb = await screen.findByLabelText('Tickets SAV')
    await user.click(ticketsCb)
    await user.click(screen.getByRole('button', { name: 'Suivant' }))
    expect(await screen.findByText(/2 jeux de données sélectionnés sur 3/)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /Lancer l'export/ }))
    await waitFor(() => expect(parametresApi.declencherExportReversibilite).toHaveBeenCalledWith(
      expect.arrayContaining(['crm_leads', 'ventes_devis']),
    ))
    const appels = parametresApi.declencherExportReversibilite.mock.calls
    const payload = appels[appels.length - 1][0]
    expect(payload).not.toContain('sav_tickets')
  })
})
