import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'

const mocks = vi.hoisted(() => ({
  comptesList: vi.fn(),
  mouvementsList: vi.fn(),
  crediter: vi.fn(),
  reglesList: vi.fn(),
}))

vi.mock('../../api/marketingApi', () => ({
  default: {
    unwrapList: (res) => {
      const data = res?.data
      return Array.isArray(data) ? data : (data?.results || [])
    },
    comptesFidelite: { list: mocks.comptesList, crediter: mocks.crediter },
    mouvementsFidelite: { list: mocks.mouvementsList },
    reglesUpsell: { list: mocks.reglesList, create: vi.fn(), update: vi.fn() },
  },
}))

import FideliteList from './FideliteList'

beforeEach(() => {
  vi.clearAllMocks()
  mocks.comptesList.mockResolvedValue({
    data: [{ id: 1, client_id: 42, points: 350, palier: 'argent' }],
  })
  mocks.mouvementsList.mockResolvedValue({
    data: [{ id: 1, points: 100, motif: 'Parrainage', date_creation: '2026-06-01T00:00:00Z' }],
  })
  mocks.reglesList.mockResolvedValue({ data: [] })
})

describe('FideliteList', () => {
  it('affiche le solde de points et le palier d\'un client', async () => {
    render(<FideliteList />)
    expect(await screen.findByText('Client #42')).toBeInTheDocument()
    expect(screen.getByText('350')).toBeInTheDocument()
    expect(screen.getByText('Argent')).toBeInTheDocument()
  })

  it('ouvrir une ligne charge et affiche son historique de mouvements', async () => {
    render(<FideliteList />)
    const row = await screen.findByTestId('fidelite-row')
    fireEvent.click(row)
    await waitFor(() => expect(mocks.mouvementsList).toHaveBeenCalledWith({ compte: 1 }))
    expect(await screen.findByText('+100')).toBeInTheDocument()
    expect(screen.getByText('Parrainage')).toBeInTheDocument()
  })

  it('créditer des points appelle crediter() puis recharge', async () => {
    mocks.crediter.mockResolvedValue({ data: {} })
    render(<FideliteList />)
    fireEvent.click(await screen.findByTestId('fidelite-row'))
    await screen.findByTestId('fidelite-crediter')
    fireEvent.change(screen.getByTestId('fidelite-credit-points'), { target: { value: '50' } })
    fireEvent.change(screen.getByTestId('fidelite-credit-motif'), { target: { value: 'Achat' } })
    fireEvent.click(screen.getByTestId('fidelite-crediter'))
    await waitFor(() => expect(mocks.crediter).toHaveBeenCalledWith(1, { points: 50, motif: 'Achat' }))
  })

  it('l\'onglet Règles d\'upsell bascule vers ReglesUpsell', async () => {
    render(<FideliteList />)
    await screen.findByText('Client #42')
    fireEvent.click(screen.getByTestId('fidelite-onglet-upsell'))
    expect(screen.queryByTestId('fidelite-table')).toBeNull()
    await waitFor(() => expect(mocks.reglesList).toHaveBeenCalled())
  })
})
