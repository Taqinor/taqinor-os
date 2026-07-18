import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { emptyForm, formFromEvenement } from './EvenementForm'

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  create: vi.fn(),
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
    evenements: { list: mocks.list, create: mocks.create },
  },
}))

import EvenementsList from './EvenementsList'

const renderScreen = () => render(<MemoryRouter><EvenementsList /></MemoryRouter>)

describe('emptyForm / formFromEvenement (logique pure)', () => {
  it('emptyForm démarre en type salon', () => {
    expect(emptyForm().type_evenement).toBe('salon')
  })

  it('formFromEvenement reprend les champs + tronque les dates ISO', () => {
    const form = formFromEvenement({
      nom: 'SIAM 2026', type_evenement: 'salon',
      date_debut: '2026-04-20T09:00:00Z', lieu: 'Meknès', capacite: 500,
    })
    expect(form.nom).toBe('SIAM 2026')
    expect(form.date_debut).toBe('2026-04-20T09:00')
    expect(form.capacite).toBe(500)
  })
})

describe('EvenementsList', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.list.mockResolvedValue({
      data: [
        { id: 1, nom: 'SIAM 2026', type_evenement: 'salon', type_display: 'Salon',
          date_debut: '2026-04-20T09:00:00Z', nb_inscrits: 12 },
      ],
    })
  })

  it('affiche les événements chargés', async () => {
    renderScreen()
    expect(await screen.findByText('SIAM 2026')).toBeInTheDocument()
  })

  it('cliquer une ligne navigue vers le détail', async () => {
    renderScreen()
    const row = await screen.findByText('SIAM 2026')
    fireEvent.click(row.closest('tr'))
    expect(mocks.navigate).toHaveBeenCalledWith('/marketing/evenements/1')
  })

  it('créer un événement appelle create() et recharge la liste', async () => {
    mocks.create.mockResolvedValue({ data: {} })
    renderScreen()
    await screen.findByText('SIAM 2026')
    fireEvent.click(screen.getByTestId('evenements-nouveau'))
    fireEvent.change(screen.getByTestId('evenement-nom'), { target: { value: 'Porte ouverte Agadir' } })
    fireEvent.change(screen.getByTestId('evenement-date-debut'), { target: { value: '2026-08-01T10:00' } })
    fireEvent.click(screen.getByTestId('evenement-save'))
    await waitFor(() => expect(mocks.create).toHaveBeenCalled())
    expect(mocks.create.mock.calls[0][0].nom).toBe('Porte ouverte Agadir')
  })
})
