import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  create: vi.fn(),
  update: vi.fn(),
}))

vi.mock('../../api/marketingApi', () => ({
  default: {
    unwrapList: (res) => {
      const data = res?.data
      return Array.isArray(data) ? data : (data?.results || [])
    },
    reglesUpsell: { list: mocks.list, create: mocks.create, update: mocks.update },
  },
}))

import ReglesUpsell from './ReglesUpsell'

beforeEach(() => {
  vi.clearAllMocks()
  mocks.list.mockResolvedValue({
    data: [{
      id: 1, declencheur: 'sans_batterie', produit_suggere: 'Batterie 5kWh',
      message: 'Ajoutez une batterie', priorite: 3, actif: true,
    }],
  })
})

describe('ReglesUpsell', () => {
  it('affiche les règles existantes', async () => {
    render(<ReglesUpsell />)
    expect(await screen.findByText('Batterie 5kWh')).toBeInTheDocument()
    expect(screen.getByText('Client sans batterie')).toBeInTheDocument()
  })

  it('créer une règle appelle create() puis recharge', async () => {
    mocks.create.mockResolvedValue({ data: {} })
    render(<ReglesUpsell />)
    await screen.findByText('Batterie 5kWh')
    fireEvent.change(screen.getByTestId('regle-produit'), { target: { value: 'Contrat O&M' } })
    fireEvent.change(screen.getByTestId('regle-priorite'), { target: { value: '5' } })
    fireEvent.click(screen.getByTestId('regle-creer'))
    await waitFor(() => expect(mocks.create).toHaveBeenCalled())
    expect(mocks.create.mock.calls[0][0].produit_suggere).toBe('Contrat O&M')
    expect(mocks.create.mock.calls[0][0].priorite).toBe(5)
  })

  it('basculer actif/inactif appelle update() avec le flag inversé', async () => {
    mocks.update.mockResolvedValue({ data: {} })
    render(<ReglesUpsell />)
    await screen.findByText('Batterie 5kWh')
    fireEvent.click(screen.getByTestId('regle-toggle'))
    await waitFor(() => expect(mocks.update).toHaveBeenCalledWith(1, { actif: false }))
  })
})
