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

const { getEquipes, saveEquipe, deleteEquipe } = vi.hoisted(() => ({
  getEquipes: vi.fn(),
  saveEquipe: vi.fn(() => Promise.resolve({ data: {} })),
  deleteEquipe: vi.fn(() => Promise.resolve({ data: {} })),
}))

vi.mock('../../api/installationsApi', () => ({
  default: {
    getEquipesTerrain: getEquipes,
    saveEquipeTerrain: saveEquipe,
    deleteEquipeTerrain: deleteEquipe,
  },
}))

import EquipeTerrainSection from './EquipeTerrainSection'

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
