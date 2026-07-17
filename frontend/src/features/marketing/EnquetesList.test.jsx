import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
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
    enquetes: { list: mocks.list },
  },
}))

import EnquetesList from './EnquetesList'

const renderScreen = () => render(<MemoryRouter><EnquetesList /></MemoryRouter>)

beforeEach(() => {
  vi.clearAllMocks()
  mocks.list.mockResolvedValue({
    data: [{ id: 1, titre: 'Satisfaction post-install', questions: [{}, {}], actif: true }],
  })
})

describe('EnquetesList', () => {
  it('affiche les enquêtes chargées', async () => {
    renderScreen()
    expect(await screen.findByText('Satisfaction post-install')).toBeInTheDocument()
  })

  it('« Nouvelle enquête » ouvre le constructeur', async () => {
    renderScreen()
    await screen.findByText('Satisfaction post-install')
    fireEvent.click(screen.getByTestId('enquetes-nouvelle'))
    expect(screen.getByTestId('enquete-builder')).toBeInTheDocument()
  })

  it('cliquer une ligne navigue vers les résultats', async () => {
    renderScreen()
    const row = await screen.findByText('Satisfaction post-install')
    fireEvent.click(row.closest('tr'))
    expect(mocks.navigate).toHaveBeenCalledWith('/marketing/enquetes/1')
  })
})
