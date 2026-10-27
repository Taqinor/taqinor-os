import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* WIR112 — Équipes terrain canoniques (DC40) : CRUD depuis Paramètres. */

const EQUIPES = [
  { id: 1, nom: 'Équipe Nord', membres: [10], chef: 10, nb_membres: 1, actif: true },
  { id: 2, nom: 'Équipe Sud', membres: [], chef: null, nb_membres: 0, actif: false },
]
const USERS = [
  { id: 10, username: 'ahmed' },
  { id: 11, username: 'sara' },
]

const { getEquipes, saveEquipe, deleteEquipe, apiGet, getEquipesCom } = vi.hoisted(() => ({
  getEquipes: vi.fn(),
  saveEquipe: vi.fn(() => Promise.resolve({ data: {} })),
  deleteEquipe: vi.fn(() => Promise.resolve({ data: {} })),
  apiGet: vi.fn(),
  getEquipesCom: vi.fn(),
}))

vi.mock('../../api/axios', () => ({ default: { get: apiGet, patch: vi.fn() } }))
vi.mock('../../api/crmApi', () => ({ default: { getEquipes: getEquipesCom } }))

vi.mock('../../api/installationsApi', () => ({
  default: {
    getEquipesTerrain: getEquipes,
    saveEquipeTerrain: saveEquipe,
    deleteEquipeTerrain: deleteEquipe,
  },
}))

import EquipeTerrainSection from './EquipeTerrainSection'
import EquipeSection from './EquipeSection'

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('EquipeTerrainSection (WIR112)', () => {
  it('liste les équipes terrain avec membres et état', async () => {
    getEquipes.mockResolvedValue({ data: EQUIPES })
    render(<EquipeTerrainSection assignables={USERS} />)
    expect(await screen.findByDisplayValue('Équipe Nord')).toBeInTheDocument()
    expect(screen.getByDisplayValue('Équipe Sud')).toBeInTheDocument()
    // Distinct des équipes commerciales/projet — titre propre.
    expect(screen.getByText('Équipes terrain')).toBeInTheDocument()
    expect(screen.getByText('1 membre(s)')).toBeInTheDocument()
  })

  it('crée une équipe terrain', async () => {
    getEquipes.mockResolvedValue({ data: [] })
    const user = userEvent.setup()
    render(<EquipeTerrainSection assignables={USERS} />)
    await screen.findByPlaceholderText('Nouvelle équipe terrain')
    await user.type(screen.getByPlaceholderText('Nouvelle équipe terrain'), 'Équipe Test')
    await user.keyboard('{Enter}')
    await waitFor(() => expect(saveEquipe).toHaveBeenCalledWith(null, { nom: 'Équipe Test' }))
  })

  it('bascule un membre dans une équipe', async () => {
    getEquipes.mockResolvedValue({ data: EQUIPES })
    const user = userEvent.setup()
    render(<EquipeTerrainSection assignables={USERS} />)
    const row = await screen.findByTestId('equipe-terrain-1')
    // sara (id 11) n'est pas membre → clic ajoute.
    await user.click(within(row).getByRole('button', { name: 'sara' }))
    await waitFor(() => expect(saveEquipe).toHaveBeenCalledWith(1, { membres: [10, 11] }))
  })
})

/* Vue « Organisation » (EquipeSection) : Direction, équipes commerciales/terrain, sans équipe. */

const USERS_ORG = [
  { id: 1, username: 'reda', role_nom: 'Directeur', is_active: true, supervisor: null },
  { id: 2, username: 'meryem', role_nom: 'Commercial responsable', is_active: true, supervisor: 1 },
  { id: 3, username: 'amine', role_nom: 'Commercial', is_active: true, supervisor: 2 },
  { id: 4, username: 'yassine', role_nom: 'Technicien', is_active: true, supervisor: null },
  { id: 5, username: 'khalid', role_nom: 'Technicien', is_active: true, supervisor: null },
  { id: 6, username: 'ancien', role_nom: 'Commercial', is_active: false, supervisor: null },
]

describe('EquipeSection — Organisation', () => {
  it('regroupe Direction, équipes et personnes sans équipe', async () => {
    apiGet.mockResolvedValue({ data: USERS_ORG })
    getEquipesCom.mockResolvedValue({ data: [
      { id: 7, nom: 'Casa', actif: true, responsable: 2, membres: [3], recoit_leads: true },
    ] })
    getEquipes.mockResolvedValue({ data: [
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
