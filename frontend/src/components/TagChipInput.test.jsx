import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

vi.mock('../api/recordsApi', () => ({
  default: {
    getTaggedItems: vi.fn(),
    getTags: vi.fn(() => Promise.resolve({ data: [] })),
    addTag: vi.fn(),
    removeTag: vi.fn(),
    createTag: vi.fn(),
  },
}))

import recordsApi from '../api/recordsApi'
import TagChipInput from './TagChipInput'

beforeEach(() => { vi.clearAllMocks() })

// AERR63 — chaque échec était avalé par un catch vide : le ticket semblait
// sans étiquette.
describe('TagChipInput (AERR63)', () => {
  it('lecture rejetée : avis + Réessayer', async () => {
    recordsApi.getTaggedItems.mockRejectedValueOnce(new Error('boom'))
    render(<TagChipInput model="sav.ticket" id={1} />)

    expect(await screen.findByRole('alert')).toHaveTextContent('Étiquettes non chargées.')

    recordsApi.getTaggedItems.mockResolvedValueOnce({ data: [{ id: 3, tag: 9, tag_nom: 'Urgent' }] })
    fireEvent.click(screen.getByRole('button', { name: 'Réessayer' }))

    expect(await screen.findByText('Urgent')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('retrait rejeté : l’étiquette reste affichée', async () => {
    recordsApi.getTaggedItems.mockResolvedValueOnce({ data: [{ id: 3, tag: 9, tag_nom: 'Urgent' }] })
    recordsApi.removeTag.mockRejectedValueOnce(new Error('403'))
    render(<TagChipInput model="sav.ticket" id={1} />)
    await screen.findByText('Urgent')

    fireEvent.click(screen.getByTitle('Retirer le tag'))

    await waitFor(() => expect(recordsApi.removeTag).toHaveBeenCalledWith(3))
    expect(screen.getByText('Urgent')).toBeInTheDocument()
  })
})
