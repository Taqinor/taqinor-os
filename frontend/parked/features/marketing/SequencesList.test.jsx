import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  create: vi.fn(),
  update: vi.fn(),
  navigate: vi.fn(),
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useNavigate: () => mocks.navigate }
})

vi.mock('../../api/marketingApi', () => ({
  default: {
    unwrapList: (res) => {
      const data = res?.data
      return Array.isArray(data) ? data : (data?.results || [])
    },
    sequences: { list: mocks.list, create: mocks.create, update: mocks.update },
  },
}))

import SequencesList from './SequencesList'

const renderScreen = () => render(<MemoryRouter><SequencesList /></MemoryRouter>)

beforeEach(() => {
  vi.clearAllMocks()
  mocks.list.mockResolvedValue({
    data: [
      { id: 1, nom: 'Onboarding partenaire', stage_declencheur: '', actif: false, etapes: [{}, {}] },
      { id: 2, nom: 'Relance devis', stage_declencheur: 'quote_sent', actif: true, etapes: [{}] },
    ],
  })
})

describe('SequencesList', () => {
  it('affiche les séquences avec leur statut et nombre d\'étapes', async () => {
    renderScreen()
    expect(await screen.findByText('Onboarding partenaire')).toBeInTheDocument()
    expect(screen.getByText('Relance devis')).toBeInTheDocument()
    const rows = screen.getAllByTestId('sequence-row')
    expect(rows[0]).toHaveTextContent('Inactive')
    expect(rows[1]).toHaveTextContent('Active')
  })

  it('« Activer une recette » n\'apparaît que sur une séquence inactive', async () => {
    renderScreen()
    await screen.findByText('Onboarding partenaire')
    expect(screen.getAllByTestId('sequence-activer')).toHaveLength(1)
  })

  it('activer une recette seedée fait un PATCH actif:true puis recharge', async () => {
    mocks.update.mockResolvedValue({ data: {} })
    renderScreen()
    await screen.findByText('Onboarding partenaire')
    fireEvent.click(screen.getByTestId('sequence-activer'))
    await waitFor(() => expect(mocks.update).toHaveBeenCalledWith(1, { actif: true }))
    await waitFor(() => expect(mocks.list).toHaveBeenCalledTimes(2))
  })

  it('cliquer une ligne navigue vers le détail', async () => {
    renderScreen()
    const row = await screen.findByText('Relance devis')
    fireEvent.click(row.closest('tr'))
    expect(mocks.navigate).toHaveBeenCalledWith('/marketing/sequences/2')
  })

  it('créer une séquence appelle create() puis recharge', async () => {
    mocks.create.mockResolvedValue({ data: {} })
    renderScreen()
    await screen.findByText('Onboarding partenaire')
    fireEvent.change(screen.getByTestId('sequence-nom'), { target: { value: 'Nouvelle séquence' } })
    fireEvent.click(screen.getByTestId('sequence-creer'))
    await waitFor(() => expect(mocks.create).toHaveBeenCalled())
    expect(mocks.create.mock.calls[0][0].nom).toBe('Nouvelle séquence')
  })
})
