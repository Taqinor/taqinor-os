import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, within } from '@testing-library/react'

/* Vue « Organisation » : Direction, équipes commerciales/terrain, sans équipe. */

const USERS = [
  { id: 1, username: 'reda', role_nom: 'Directeur', is_active: true, supervisor: null },
  { id: 2, username: 'meryem', role_nom: 'Commercial responsable', is_active: true, supervisor: 1 },
  { id: 3, username: 'amine', role_nom: 'Commercial', is_active: true, supervisor: 2 },
  { id: 4, username: 'yassine', role_nom: 'Technicien', is_active: true, supervisor: null },
  { id: 5, username: 'khalid', role_nom: 'Technicien', is_active: true, supervisor: null },
  { id: 6, username: 'ancien', role_nom: 'Commercial', is_active: false, supervisor: null },
]

const { apiGet, getEquipes, getEquipesTerrain } = vi.hoisted(() => ({
  apiGet: vi.fn(),
  getEquipes: vi.fn(),
  getEquipesTerrain: vi.fn(),
}))

vi.mock('../../api/axios', () => ({ default: { get: apiGet, patch: vi.fn() } }))
vi.mock('../../api/crmApi', () => ({ default: { getEquipes } }))
vi.mock('../../api/installationsApi', () => ({ default: { getEquipesTerrain } }))

import EquipeSection from './EquipeSection'

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('EquipeSection — Organisation', () => {
  it('regroupe Direction, équipes et personnes sans équipe', async () => {
    apiGet.mockResolvedValue({ data: USERS })
    getEquipes.mockResolvedValue({ data: [
      { id: 7, nom: 'Casa', actif: true, responsable: 2, membres: [3], recoit_leads: true },
    ] })
    getEquipesTerrain.mockResolvedValue({ data: [
      { id: 8, nom: 'Nord', actif: true, chef: 4, membres: [] },
    ] })
    render(<EquipeSection />)

    const direction = await screen.findByRole('region', { name: 'Direction' })
    expect(within(direction).getByText('reda')).toBeInTheDocument()

    const com = await screen.findByTestId('org-equipe-7')
    expect(within(com).getByText('Reçoit les nouveaux leads')).toBeInTheDocument()
    expect(within(com).getByText(/défini par l'équipe Casa/)).toBeInTheDocument()

    expect(screen.getByTestId('org-equipe-8')).toBeInTheDocument()

    const sans = screen.getByRole('region', { name: 'Sans équipe' })
    expect(within(sans).getByText('khalid')).toBeInTheDocument()
    const noms = within(sans).getAllByRole('listitem').map((li) => li.querySelector('span').textContent)
    // ni l'inactif (ancien), ni le membre d'équipe (amine), ni le chef (yassine)
    expect(noms).toEqual(['khalid'])
    expect(within(sans).getByLabelText('Superviseur de khalid')).toBeInTheDocument()
  })
})
