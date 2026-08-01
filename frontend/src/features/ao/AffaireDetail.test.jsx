import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  getComments: vi.fn(),
  getAttachments: vi.fn(),
  createComment: vi.fn(),
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useParams: () => ({ id: '1' }) }
})

vi.mock('../../api/aoApi', () => ({
  default: { affaires: { get: mocks.get } },
}))

vi.mock('../../api/recordsApi', () => ({
  default: {
    getComments: mocks.getComments,
    getAttachments: mocks.getAttachments,
    createComment: mocks.createComment,
  },
}))

import AffaireDetail from './AffaireDetail'

const renderScreen = () => render(<MemoryRouter><AffaireDetail /></MemoryRouter>)

const AFFAIRE = {
  id: 1, reference: 'AO-2026-001', objet: 'Centrale solaire école',
  acheteur: 'Commune X', type_marche: 'public', type_marche_display: 'Public',
  lot: 'Lot 1', date_limite: '2026-09-15', montant_estime: 1500000,
  caution_provisoire: 30000, statut: 'depose',
  verdict_global: 'confirme', verdict_global_label: 'Confirmé',
  prochaine_echeance_libelle: 'Remise des plis', prochaine_echeance_date: '2026-09-15',
  dossier_completude: 62, resultat_issue_display: null,
}

const COMMENTS = [
  { id: 10, body: 'Visite de site effectuée.', author_display: 'Reda Kasri', created_at: '2026-08-01T10:00:00Z' },
]

beforeEach(() => {
  vi.clearAllMocks()
  mocks.get.mockResolvedValue({ data: AFFAIRE })
  mocks.getComments.mockResolvedValue({ data: COMMENTS })
  mocks.getAttachments.mockResolvedValue({ data: [] })
  mocks.createComment.mockResolvedValue({ data: {} })
})

describe('AffaireDetail', () => {
  it('charge la fiche via aoApi.affaires.get(id) et affiche référence/objet/statut', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.get).toHaveBeenCalledWith('1'))
    expect(await screen.findByText('AO-2026-001')).toBeInTheDocument()
    expect(screen.getByText('Centrale solaire école')).toBeInTheDocument()
    expect(screen.getByText('Déposé')).toBeInTheDocument()
  })

  it('affiche les 7 onglets attendus (Synthèse, Toitures & relevés, Calepinages, Bordereau, Dossier, Questions terrain, Historique)', async () => {
    renderScreen()
    await screen.findByText('AO-2026-001')
    for (const label of [
      'Synthèse', 'Toitures & relevés', 'Calepinages', 'Bordereau',
      'Dossier', 'Questions terrain', 'Historique',
    ]) {
      expect(screen.getByRole('tab', { name: label })).toBeInTheDocument()
    }
  })

  it('n’a JAMAIS un onglet ou un mot « rentabilité » dans l’arbre (route séparée AOF161)', async () => {
    renderScreen()
    await screen.findByText('AO-2026-001')
    expect(screen.queryByText(/rentabilit/i)).toBeNull()
    expect(screen.queryByRole('tab', { name: /rentabilit/i })).toBeNull()
  })

  it('le bandeau de verdict affiche verdict/échéance/complétude issus tels quels de l’affaire (aucun calcul de KPI)', async () => {
    renderScreen()
    await screen.findByText('AO-2026-001')
    expect(screen.getByText('Confirmé')).toBeInTheDocument()
    expect(screen.getByText('Remise des plis')).toBeInTheDocument()
    expect(screen.getByText('62 %')).toBeInTheDocument()
  })

  it('le bandeau retombe sur « — » quand un champ agrégé est absent (jamais un calcul de substitution)', async () => {
    mocks.get.mockResolvedValue({
      data: { ...AFFAIRE, verdict_global: null, verdict_global_label: null, dossier_completude: null, resultat_issue_display: null },
    })
    renderScreen()
    await screen.findByText('AO-2026-001')
    expect(screen.getAllByText('—').length).toBeGreaterThan(0)
  })

  it('le chatter (ChatterTimeline, cible ao.appeloffre) affiche les notes de records', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.getComments).toHaveBeenCalledWith('ao.appeloffre', '1'))
    expect(await screen.findAllByText(/Visite de site effectuée/)).not.toHaveLength(0)
  })

  it('ajouter une note appelle recordsApi.createComment(ao.appeloffre, id, texte) et vide le champ', async () => {
    renderScreen()
    await screen.findByText('AO-2026-001')
    const textarea = screen.getByLabelText('Nouvelle note')
    fireEvent.change(textarea, { target: { value: 'Nouvelle observation terrain.' } })
    fireEvent.click(screen.getByRole('button', { name: /Noter/i }))
    await waitFor(() => expect(mocks.createComment).toHaveBeenCalledWith(
      'ao.appeloffre', '1', 'Nouvelle observation terrain.',
    ))
    await waitFor(() => expect(textarea.value).toBe(''))
  })
})
