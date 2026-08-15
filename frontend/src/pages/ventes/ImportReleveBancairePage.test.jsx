// WIR265/FG42 — écran consommateur du couple dry-run / commit d'import de
// relevé bancaire. Le dry-run n'écrit RIEN ; le commit crée les encaissements.

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

vi.mock('../../api/ventesApi', () => ({
  default: {
    importReleveDryRun: vi.fn(),
    importReleveCommit: vi.fn(),
  },
}))

import ventesApi from '../../api/ventesApi'
import ImportReleveBancairePage from './ImportReleveBancairePage'

beforeEach(() => { vi.clearAllMocks() })

const renderPage = () => render(
  <MemoryRouter><ImportReleveBancairePage /></MemoryRouter>,
)

const fichier = () => new File(['ref;montant\nFA-1;100'], 'releve.csv', { type: 'text/csv' })

const choisir = () => {
  const input = screen.getByLabelText(/Fichier de relevé/)
  fireEvent.change(input, { target: { files: [fichier()] } })
}

const APERCU = {
  columns: { Référence: 'reference', Montant: 'montant' },
  unmapped: ['Libellé banque'],
  preview: [
    {
      ligne: 2, date: '2026-07-01', reference: 'FA-2026-07-0001',
      montant: '1200.00', statut: 'a_importer',
      facture_reference: 'FA-2026-07-0001', match_type: 'reference',
    },
    {
      ligne: 3, date: '2026-07-02', reference: 'XXX', montant: '50.00',
      statut: 'non_trouve', facture_reference: null, match_type: null,
    },
  ],
  total_rows: 2, matched: 1, already_paid: 0,
}

describe('ImportReleveBancairePage (WIR265)', () => {
  it("l'analyse appelle le dry-run et n'importe rien", async () => {
    ventesApi.importReleveDryRun.mockResolvedValue({ data: APERCU })
    renderPage()
    choisir()
    fireEvent.click(screen.getByRole('button', { name: 'Analyser' }))

    await waitFor(() => expect(ventesApi.importReleveDryRun).toHaveBeenCalledTimes(1))
    // Le dry-run n'écrit RIEN : aucun commit déclenché par l'analyse.
    expect(ventesApi.importReleveCommit).not.toHaveBeenCalled()

    // Mapping, colonnes ignorées, totaux et statut par ligne sont rendus.
    expect(await screen.findByText(/Référence → reference/)).toBeInTheDocument()
    expect(screen.getByText(/Libellé banque/)).toBeInTheDocument()
    expect(screen.getByText('À importer')).toBeInTheDocument()
    expect(screen.getByText('Facture introuvable')).toBeInTheDocument()
  })

  it('le commit crée les encaissements et affiche le bilan', async () => {
    ventesApi.importReleveDryRun.mockResolvedValue({ data: APERCU })
    ventesApi.importReleveCommit.mockResolvedValue({
      data: { created: 1, skipped: 1, errors: 0, results: [] },
    })
    renderPage()
    choisir()
    fireEvent.click(screen.getByRole('button', { name: 'Analyser' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Importer' }))

    await waitFor(() => expect(ventesApi.importReleveCommit).toHaveBeenCalledTimes(1))
    expect(await screen.findByText(/Résultat de l'import/)).toBeInTheDocument()
    expect(screen.getByText(/encaissement\(s\) créé\(s\)/)).toBeInTheDocument()
  })

  it('un 400 serveur est affiché en français, jamais du JSON brut', async () => {
    ventesApi.importReleveDryRun.mockRejectedValue({
      response: { status: 400, data: { detail: 'Lecture du fichier impossible (format invalide ?).' } },
    })
    renderPage()
    choisir()
    fireEvent.click(screen.getByRole('button', { name: 'Analyser' }))

    expect(await screen.findByRole('alert'))
      .toHaveTextContent(/Lecture du fichier impossible/)
    // Pas d'aperçu affiché quand l'analyse a échoué → pas de bouton Importer.
    expect(screen.queryByRole('button', { name: 'Importer' })).toBeNull()
  })

  it('changer de fichier invalide l’aperçu précédent (pas d’import à l’aveugle)', async () => {
    ventesApi.importReleveDryRun.mockResolvedValue({ data: APERCU })
    renderPage()
    choisir()
    fireEvent.click(screen.getByRole('button', { name: 'Analyser' }))
    expect(await screen.findByRole('button', { name: 'Importer' })).toBeInTheDocument()

    choisir()
    await waitFor(() =>
      expect(screen.queryByRole('button', { name: 'Importer' })).toBeNull())
  })

  it('sans fichier choisi, « Analyser » reste désactivé', () => {
    renderPage()
    expect(screen.getByRole('button', { name: 'Analyser' })).toBeDisabled()
    expect(ventesApi.importReleveDryRun).not.toHaveBeenCalled()
  })
})
