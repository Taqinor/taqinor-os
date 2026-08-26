import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* WIR265/FG42 — Le couple d'endpoints multipart d'import de relevé bancaire
   (dry-run puis commit) existait et était testé côté serveur SANS aucun
   consommateur : rapprocher un relevé se faisait paiement par paiement, à la
   main. L'assistant vit ici, en DEUX étapes — l'aperçu n'écrit rien, et
   l'import n'est déclenchable qu'après l'avoir vu. */

vi.mock('../../api/ventesApi', () => ({
  default: {
    getPaiements: vi.fn(() => Promise.resolve({ data: [] })),
    importReleveDryRun: vi.fn(),
    importReleveCommit: vi.fn(),
  },
}))

import ventesApi from '../../api/ventesApi'
import PaiementsPage from './PaiementsPage'

const APERCU = {
  columns: { Date: 'date', Libellé: 'reference', Montant: 'montant' },
  unmapped: ['Solde'],
  total_rows: 3,
  matched: 2,
  already_paid: 1,
  preview: [
    {
      ligne: 2, date: '2026-08-01', reference: 'FAC-2026-0001',
      montant: '5000.00', statut: 'a_importer',
      facture_reference: 'FAC-2026-0001', match_type: 'reference',
    },
    {
      ligne: 3, date: '2026-08-02', reference: 'FAC-2026-0002',
      montant: '1200.00', statut: 'deja_regle',
      facture_reference: 'FAC-2026-0002', match_type: 'reference',
    },
    {
      ligne: 4, date: '2026-08-03', reference: 'INCONNU',
      montant: '900.00', statut: 'non_trouve',
      facture_reference: null, match_type: null,
    },
  ],
}

const fichier = () => new File(['a;b'], 'releve.csv', { type: 'text/csv' })

function renderPage(chemin = '/ventes/paiements/import-releve') {
  return render(
    <MemoryRouter initialEntries={[chemin]}>
      <PaiementsPage />
    </MemoryRouter>,
  )
}

const deposer = (dialog) => {
  const input = within(dialog).getByLabelText('Fichier du relevé')
  fireEvent.change(input, { target: { files: [fichier()] } })
}

beforeEach(() => {
  vi.clearAllMocks()
  ventesApi.getPaiements.mockResolvedValue({ data: [] })
})

describe('PaiementsPage — WIR265 : import de relevé bancaire', () => {
  it('la route /import-releve ouvre l’assistant', async () => {
    renderPage()
    expect(await screen.findByRole('dialog')).toBeInTheDocument()
    expect(screen.getByText('Importer un relevé bancaire')).toBeInTheDocument()
  })

  it('l’écran des encaissements seul n’ouvre PAS l’assistant', async () => {
    renderPage('/ventes/paiements')
    await waitFor(() => expect(ventesApi.getPaiements).toHaveBeenCalled())
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('« Importer » reste bloqué tant que l’aperçu n’a pas été fait', async () => {
    const dialog = await (renderPage(), screen.findByRole('dialog'))
    // Sans fichier : les deux actions sont fermées.
    expect(within(dialog).getByRole('button', { name: /Aperçu/ })).toBeDisabled()
    expect(within(dialog).getByRole('button', { name: 'Importer' })).toBeDisabled()
    deposer(dialog)
    // Fichier choisi : l'aperçu s'ouvre, l'import reste fermé.
    expect(within(dialog).getByRole('button', { name: /Aperçu/ })).not.toBeDisabled()
    expect(within(dialog).getByRole('button', { name: 'Importer' })).toBeDisabled()
    expect(ventesApi.importReleveCommit).not.toHaveBeenCalled()
  })

  it('l’aperçu appelle le dry-run et n’écrit RIEN', async () => {
    ventesApi.importReleveDryRun.mockResolvedValue({ data: APERCU })
    const dialog = await (renderPage(), screen.findByRole('dialog'))
    deposer(dialog)
    fireEvent.click(within(dialog).getByRole('button', { name: /Aperçu/ }))

    await waitFor(() => expect(ventesApi.importReleveDryRun).toHaveBeenCalled())
    // Le wrapper reçoit le FICHIER (il construit le FormData `file` lui-même).
    expect(ventesApi.importReleveDryRun.mock.calls[0][0]).toBeInstanceOf(File)
    // Aucun commit, et aucun rechargement de la liste : rien n'a été écrit.
    expect(ventesApi.importReleveCommit).not.toHaveBeenCalled()
    expect(ventesApi.getPaiements).toHaveBeenCalledTimes(1)

    // Mapping, statuts et totaux viennent tous du serveur.
    expect(await screen.findByText('Date → date')).toBeInTheDocument()
    expect(screen.getByText(/Ignorées : Solde/)).toBeInTheDocument()
    expect(screen.getByText('À importer')).toBeInTheDocument()
    expect(screen.getByText('Déjà réglée')).toBeInTheDocument()
    expect(screen.getByText('Facture non trouvée')).toBeInTheDocument()
  })

  it('l’import crée les paiements puis recharge la liste', async () => {
    ventesApi.importReleveDryRun.mockResolvedValue({ data: APERCU })
    ventesApi.importReleveCommit.mockResolvedValue({
      data: { created: 2, skipped: 1, errors: 0, results: [] },
    })
    const dialog = await (renderPage(), screen.findByRole('dialog'))
    deposer(dialog)
    fireEvent.click(within(dialog).getByRole('button', { name: /Aperçu/ }))
    await screen.findByText('À importer')

    fireEvent.click(within(dialog).getByRole('button', { name: 'Importer' }))
    await waitFor(() => expect(ventesApi.importReleveCommit).toHaveBeenCalled())
    expect(await screen.findByText(/encaissement\(s\) créé\(s\)/)).toBeInTheDocument()
    // La liste est rechargée : les paiements créés sont visibles sans F5.
    await waitFor(() => expect(ventesApi.getPaiements).toHaveBeenCalledTimes(2))
  })

  it('un 400 serveur est affiché TEL QUEL', async () => {
    ventesApi.importReleveDryRun.mockRejectedValue({
      response: { data: { detail: 'Fichier trop volumineux (max 5 Mo, reçu 9000000 octets).' } },
    })
    const dialog = await (renderPage(), screen.findByRole('dialog'))
    deposer(dialog)
    fireEvent.click(within(dialog).getByRole('button', { name: /Aperçu/ }))
    expect(await screen.findByText(/Fichier trop volumineux \(max 5 Mo/))
      .toBeInTheDocument()
    // L'import reste fermé : sans aperçu, pas d'écriture.
    expect(within(dialog).getByRole('button', { name: 'Importer' })).toBeDisabled()
  })
})
