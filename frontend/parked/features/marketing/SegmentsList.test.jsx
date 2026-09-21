import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  create: vi.fn(),
  update: vi.fn(),
  previsualiser: vi.fn(),
}))

vi.mock('../../api/marketingApi', () => ({
  default: {
    unwrapList: (res) => {
      const data = res?.data
      return Array.isArray(data) ? data : (data?.results || [])
    },
    segments: {
      list: mocks.list, create: mocks.create, update: mocks.update,
      previsualiser: mocks.previsualiser,
    },
  },
}))

import SegmentsList from './SegmentsList'

beforeEach(() => {
  vi.clearAllMocks()
  mocks.update.mockResolvedValue({ data: {} })
  mocks.previsualiser.mockResolvedValue({ data: { count: 0, echantillon: [] } })
  mocks.list.mockResolvedValue({
    data: [
      { id: 1, nom: 'Leads chauds', regles: { score: { gte: 70 } } },
      { id: 2, nom: 'Sans règle', regles: {} },
    ],
  })
})

describe('SegmentsList', () => {
  it('affiche les segments existants avec leur nombre de critères', async () => {
    render(<SegmentsList />)
    expect(await screen.findByText('Leads chauds')).toBeInTheDocument()
    const rows = screen.getAllByTestId('segment-row')
    expect(rows).toHaveLength(2)
    expect(rows[0]).toHaveTextContent('1 critère(s)')
    expect(rows[1]).toHaveTextContent('0 critère(s)')
  })

  it('« Nouveau segment » ouvre le constructeur', async () => {
    render(<SegmentsList />)
    await screen.findByText('Leads chauds')
    fireEvent.click(screen.getByTestId('segments-nouveau'))
    expect(screen.getByTestId('segment-builder')).toBeInTheDocument()
  })

  it('« Éditer » ouvre le constructeur avec le segment pré-rempli', async () => {
    render(<SegmentsList />)
    await screen.findByText('Leads chauds')
    fireEvent.click(screen.getAllByTestId('segment-editer')[0])
    expect(screen.getByTestId('segment-nom').value).toBe('Leads chauds')
  })

  it('fermer le constructeur recharge la liste', async () => {
    render(<SegmentsList />)
    await screen.findByText('Leads chauds')
    fireEvent.click(screen.getByTestId('segments-nouveau'))
    fireEvent.click(screen.getByText('Fermer'))
    await waitFor(() => expect(mocks.list).toHaveBeenCalledTimes(2))
  })
})
