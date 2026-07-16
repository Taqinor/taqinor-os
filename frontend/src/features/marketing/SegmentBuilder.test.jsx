import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'

const mocks = vi.hoisted(() => ({
  create: vi.fn(),
  update: vi.fn(),
  previsualiser: vi.fn(),
}))

vi.mock('../../api/marketingApi', () => ({
  default: {
    segments: {
      create: mocks.create, update: mocks.update, previsualiser: mocks.previsualiser,
    },
  },
}))

import SegmentBuilder from './SegmentBuilder'

beforeEach(() => {
  vi.clearAllMocks()
  mocks.update.mockResolvedValue({ data: {} })
  mocks.previsualiser.mockResolvedValue({ data: { count: 0, echantillon: [] } })
})

describe('SegmentBuilder (NTMKT4)', () => {
  it("sans segment créé, la prévisualisation n'apparaît pas encore", () => {
    render(<SegmentBuilder initial={null} onSaved={vi.fn()} onCancel={vi.fn()} />)
    expect(screen.queryByTestId('segment-preview-compte')).toBeNull()
    expect(screen.getByTestId('segment-creer')).toBeInTheDocument()
  })

  it('« Créer » pose le nom, crée le brouillon puis prévisualise', async () => {
    mocks.create.mockResolvedValue({ data: { id: 5 } })
    mocks.previsualiser.mockResolvedValue({ data: { count: 3, echantillon: [1, 2, 3] } })
    render(<SegmentBuilder initial={null} onSaved={vi.fn()} onCancel={vi.fn()} />)
    fireEvent.change(screen.getByTestId('segment-nom'), { target: { value: 'Leads froids' } })
    fireEvent.click(screen.getByTestId('segment-creer'))
    await waitFor(() => expect(mocks.create).toHaveBeenCalledWith(
      { nom: 'Leads froids', regles: {} }))
    expect(await screen.findByTestId('segment-preview-compte'))
      .toHaveTextContent('3 lead(s)')
  })

  it("ajouter une règle sur un segment existant re-persiste puis re-prévisualise", async () => {
    mocks.update.mockResolvedValue({ data: {} })
    mocks.previsualiser.mockResolvedValue({ data: { count: 7, echantillon: [] } })
    render(<SegmentBuilder
      initial={{ id: 9, nom: 'Segment X', regles: {} }}
      onSaved={vi.fn()} onCancel={vi.fn()} />)
    fireEvent.change(screen.getByTestId('segment-ville'), { target: { value: 'Marrakech' } })
    await waitFor(() => expect(mocks.update).toHaveBeenCalledWith(
      9, { regles: { ville: 'Marrakech' } }))
    await waitFor(() => expect(mocks.previsualiser).toHaveBeenCalledWith(9))
    expect(await screen.findByTestId('segment-preview-compte'))
      .toHaveTextContent('7 lead(s)')
  })

  it('un échec réseau affiche une erreur plutôt que de rester bloqué', async () => {
    mocks.update.mockRejectedValue(new Error('500'))
    render(<SegmentBuilder
      initial={{ id: 9, nom: 'Segment X', regles: {} }}
      onSaved={vi.fn()} onCancel={vi.fn()} />)
    fireEvent.change(screen.getByTestId('segment-ville'), { target: { value: 'Fès' } })
    await waitFor(() => expect(screen.getByText(/impossible/i)).toBeInTheDocument())
  })
})
