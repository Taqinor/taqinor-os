import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import gestionProjetApi from '../../../api/gestionProjetApi'
import RisquesPage from './RisquesPage'

/* ZPRJ7-9 — Lien d'évaluation CSAT (idempotent), rapport d'avancement PDF
   (WeasyPrint interne — jamais le moteur premium client) et heatmap des
   risques (P × I) dans RisquesPage. */

vi.mock('../../../api/gestionProjetApi', () => ({
  default: {
    getProjets: vi.fn(() => Promise.resolve({ data: [{ id: 10, code: 'P-1', nom: 'Villa Fès' }] })),
    getRisques: vi.fn(() => Promise.resolve({ data: [] })),
    getActions: vi.fn(() => Promise.resolve({ data: [] })),
    getComptesRendus: vi.fn(() => Promise.resolve({ data: [] })),
    getDocuments: vi.fn(() => Promise.resolve({ data: [] })),
    getCommentaires: vi.fn(() => Promise.resolve({ data: [] })),
    getModeles: vi.fn(() => Promise.resolve({ data: [] })),
    getSousTraitants: vi.fn(() => Promise.resolve({ data: [] })),
    getLotsSousTraitance: vi.fn(() => Promise.resolve({ data: [] })),
    getMatriceRisques: vi.fn(() => Promise.resolve({
      data: {
        grille: [{ probabilite: 4, impact: 5, nombre: 2 }],
        total_ouverts_surveilles: 2,
        top_risques: [{ id: 1, libelle: 'Retard livraison onduleur', probabilite: 4, impact: 5, criticite: 20, statut: 'ouvert' }],
      },
    })),
    getLienEvaluation: vi.fn(() => Promise.resolve({ data: { projet_id: 10, token: 'abc123', deja_soumis: false } })),
    getRapportAvancementPdf: vi.fn(() => Promise.resolve({ data: new Blob(['pdf']), headers: {} })),
  },
}))

vi.mock('../../../ui', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, toast: { success: vi.fn(), error: vi.fn() } }
})

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('RisquesPage — ZPRJ7-9', () => {
  it('affiche la matrice des risques après sélection du projet', async () => {
    const user = userEvent.setup()
    render(<RisquesPage />)
    await screen.findByRole('option', { name: /Villa Fès/ })
    await user.selectOptions(screen.getByLabelText('Projet'), '10')
    await waitFor(() => expect(gestionProjetApi.getMatriceRisques).toHaveBeenCalledWith('10'))
    await user.click(screen.getByRole('tab', { name: 'Matrice P × I' }))
    expect(await screen.findByText('Retard livraison onduleur')).toBeInTheDocument()
  })

  it('« Lien CSAT » appelle l\'action serveur dédiée', async () => {
    const user = userEvent.setup()
    render(<RisquesPage />)
    await screen.findByRole('option', { name: /Villa Fès/ })
    await user.selectOptions(screen.getByLabelText('Projet'), '10')
    await user.click(await screen.findByRole('button', { name: /Lien CSAT/ }))
    await waitFor(() => expect(gestionProjetApi.getLienEvaluation).toHaveBeenCalledWith('10'))
  })

  it('« Rapport PDF » télécharge le rapport d\'avancement', async () => {
    const user = userEvent.setup()
    render(<RisquesPage />)
    await screen.findByRole('option', { name: /Villa Fès/ })
    await user.selectOptions(screen.getByLabelText('Projet'), '10')
    await user.click(await screen.findByRole('button', { name: /Rapport PDF/ }))
    await waitFor(() => expect(gestionProjetApi.getRapportAvancementPdf).toHaveBeenCalledWith('10'))
  })
})
