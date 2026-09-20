import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  update: vi.fn(),
  lier: vi.fn(),
  delier: vi.fn(),
  checklistAjouter: vi.fn(),
  checklistCocher: vi.fn(),
  historique: vi.fn(),
  noter: vi.fn(),
  navigate: vi.fn(),
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mocks.navigate,
    useParams: () => ({ id: '5' }),
  }
})

vi.mock('../../api/coreApi', () => ({
  default: {
    dossiers: {
      get: mocks.get,
      update: mocks.update,
      lier: mocks.lier,
      delier: mocks.delier,
      checklist: { ajouter: mocks.checklistAjouter, cocher: mocks.checklistCocher },
      historique: mocks.historique,
      noter: mocks.noter,
    },
  },
}))

import DossierDetail from './DossierDetail'

const DOSSIER = {
  id: 5,
  titre: 'Réclamation client X',
  type_dossier: 'reclamation_complexe',
  type_dossier_label: 'Réclamation complexe',
  statut: 'ouvert',
  statut_label: 'Ouvert',
  priorite: 'haute',
  priorite_label: 'Haute',
  proprietaire_username: 'meryem',
  echeance: '2020-01-01', // largement dépassée -> "en retard"
  liens: [
    { id: 1, cle_modele: 'crm.lead', object_id: 42, libelle: 'Lead Bouskoura' },
    { id: 2, cle_modele: 'rh.employe', object_id: 9, libelle: '' },
  ],
  checklist: [
    { id: 10, libelle: 'Contacter le client', ordre: 0, fait: false },
    { id: 11, libelle: 'Envoyer le devis', ordre: 1, fait: true },
  ],
  etape_courante: null,
}

const renderScreen = () => render(
  <MemoryRouter><DossierDetail /></MemoryRouter>,
)

describe('DossierDetail (NTWFL19)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.get.mockResolvedValue({ data: DOSSIER })
    mocks.historique.mockResolvedValue({ data: [] })
  })

  it('affiche les objets liés cliquables et non cliquables', async () => {
    renderScreen()
    const lien = await screen.findByText('Lead Bouskoura')
    expect(lien.closest('a')).toHaveAttribute('href', '/crm/leads/42')
    // Cible sans mapping connu : affichée mais jamais un lien mort.
    const nonMappe = screen.getByText('rh.employe #9')
    expect(nonMappe.closest('a')).toBeNull()
  })

  it('affiche la checklist et le badge « en retard »', async () => {
    renderScreen()
    await screen.findByText('Contacter le client')
    expect(screen.getByText('Envoyer le devis')).toBeInTheDocument()
    expect(screen.getByText('En retard')).toBeInTheDocument()
  })

  it('cocher un item se reflète immédiatement (optimiste)', async () => {
    mocks.checklistCocher.mockResolvedValue({ data: {} })
    renderScreen()
    await screen.findByText('Contacter le client')
    const checkbox = screen.getAllByRole('checkbox')[0]
    fireEvent.click(checkbox)
    await waitFor(() => expect(mocks.checklistCocher).toHaveBeenCalledWith(5, 10, true))
    expect(checkbox).toBeChecked()
  })

  it('charge l’historique (chatter) du dossier', async () => {
    mocks.historique.mockResolvedValue({
      data: [{ id: 1, kind: 'creation', new_value: 'Réclamation client X', user_username: 'reda', created_at: '2026-09-01T10:00:00Z' }],
    })
    renderScreen()
    expect(await screen.findByText('Réclamation client X', { selector: 'p' })).toBeInTheDocument()
  })
})
