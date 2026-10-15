// ACHT62 + ACHT65 — Interventions : faux serveur DRF PAGINÉ (50) ; toutes les cartes,
// et un lien profond hors liste résolu par getIntervention(id).
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import InterventionsPage from './InterventionsPage'

vi.mock('../../api/installationsApi', () => ({
  default: {
    getInterventions: vi.fn(),
    getIntervention: vi.fn(),
    updateIntervention: vi.fn(),
    getInterventionHistorique: vi.fn(),
    noterIntervention: vi.fn(),
  },
}))
vi.mock('../../api/crmApi', () => ({ default: { getAssignableUsers: vi.fn() } }))

import installationsApi from '../../api/installationsApi'
import crmApi from '../../api/crmApi'

const PAGE_SIZE = 50
const TOUTES = Array.from({ length: 56 }, (_, i) => ({
  id: i + 1,
  installation_reference: `CH-${String(i + 1).padStart(3, '0')}`,
  client_nom: `Client ${i + 1}`,
  type_intervention: 'pose',
  statut: 'a_preparer',
}))

beforeEach(() => {
  vi.clearAllMocks()
  try { localStorage.setItem('taqinor.interventions.view', 'liste') } catch { /* indisponible */ }
  installationsApi.getInterventions.mockImplementation(({ page = 1 } = {}) => {
    const debut = (page - 1) * PAGE_SIZE
    return Promise.resolve({
      data: {
        count: TOUTES.length,
        next: debut + PAGE_SIZE < TOUTES.length ? `?page=${page + 1}` : null,
        results: TOUTES.slice(debut, debut + PAGE_SIZE),
      },
    })
  })
  installationsApi.getInterventionHistorique.mockResolvedValue({ data: [] })
  crmApi.getAssignableUsers.mockResolvedValue({ data: [] })
})

describe('InterventionsPage — ACHT62', () => {
  it('affiche les 56 interventions, pas seulement la page 1', async () => {
    render(<MemoryRouter initialEntries={['/interventions']}><InterventionsPage /></MemoryRouter>)
    await waitFor(() => expect(screen.getByText('Client 56')).toBeInTheDocument())
    expect(screen.getByText('Client 1')).toBeInTheDocument()
  })

  it('un lien profond absent de la liste est résolu par getIntervention(id)', async () => {
    installationsApi.getIntervention.mockResolvedValue({
      data: { id: 999, installation_reference: 'CH-999', client_nom: 'Client Hors Liste', type_intervention: 'pose', statut: 'a_preparer' },
    })
    render(<MemoryRouter initialEntries={['/interventions?id=999']}><InterventionsPage /></MemoryRouter>)
    await waitFor(() => expect(installationsApi.getIntervention).toHaveBeenCalledWith('999'))
    await waitFor(() => expect(screen.getAllByText(/Client Hors Liste/).length).toBeGreaterThan(0))
    expect(screen.queryByText('Intervention introuvable')).not.toBeInTheDocument()
  })

  it('getIntervention en 404 : « introuvable »', async () => {
    installationsApi.getIntervention.mockRejectedValue({ response: { status: 404 } })
    render(<MemoryRouter initialEntries={['/interventions?id=999']}><InterventionsPage /></MemoryRouter>)
    await waitFor(() => expect(screen.getByText('Intervention introuvable')).toBeInTheDocument())
  })
})

// ACHT65 — `?installation=<id>` : filtre serveur existant `installation` (faux serveur filtrant).
describe('InterventionsPage — ACHT65 ?installation=', () => {
  it('ne liste que les interventions du chantier demandé', async () => {
    const parChantier = [
      { id: 1, installation: 10, installation_reference: 'CH-010', client_nom: 'Client Dix', type_intervention: 'pose', statut: 'a_preparer' },
      { id: 2, installation: 20, installation_reference: 'CH-020', client_nom: 'Client Vingt', type_intervention: 'pose', statut: 'a_preparer' },
    ]
    installationsApi.getInterventions.mockImplementation(({ installation } = {}) => {
      const rows = parChantier.filter((x) => !installation || String(x.installation) === String(installation))
      return Promise.resolve({ data: { count: rows.length, next: null, results: rows } })
    })
    render(<MemoryRouter initialEntries={['/interventions?installation=10']}><InterventionsPage /></MemoryRouter>)
    await waitFor(() => expect(screen.getByText('Client Dix')).toBeInTheDocument())
    expect(screen.queryByText('Client Vingt')).toBeNull()
    expect(installationsApi.getInterventions).toHaveBeenCalledWith(expect.objectContaining({ installation: '10' }))
  })
})
