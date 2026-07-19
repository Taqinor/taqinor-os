import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'

/* PUB55 — Chatter d'entité : fil fusionné (note + action + alerte) + poster une
   note. */

const mocks = vi.hoisted(() => ({ timeline: vi.fn(), postNote: vi.fn() }))

vi.mock('./adsengineApi', () => ({
  default: { chatter: { timeline: mocks.timeline, postNote: mocks.postNote } },
}))

import AdChatter from './AdChatter'

const TIMELINE = [
  { kind: 'note', body: 'Budget baissé Ramadan', author: 'reda', at: '2026-03-01T10:00:00Z' },
  { kind: 'action_applied', body: 'Mettre en pause — dépense sans lead', at: '2026-02-28T09:00:00Z' },
  { kind: 'alert', body: 'Plafond dépassé', at: '2026-02-27T08:00:00Z' },
]

beforeEach(() => {
  vi.clearAllMocks()
  mocks.timeline.mockResolvedValue({ data: TIMELINE })
  mocks.postNote.mockResolvedValue({ data: { id: 5 } })
})

describe('AdChatter', () => {
  it('affiche le fil fusionné (note + action + alerte)', async () => {
    render(<AdChatter entityType="campaign" entityId="camp-1" />)
    await waitFor(() => expect(screen.getByTestId('ae-chatter-list')).toBeTruthy())
    expect(mocks.timeline).toHaveBeenCalledWith('campaign', 'camp-1')
    const list = screen.getByTestId('ae-chatter-list')
    expect(list.textContent).toContain('Budget baissé Ramadan')
    expect(list.textContent).toContain('Mettre en pause')
    expect(list.textContent).toContain('Plafond dépassé')
  })

  it('poste une note manuelle et recharge', async () => {
    render(<AdChatter entityType="ad" entityId="ad-7" />)
    await waitFor(() => expect(screen.getByTestId('ae-chatter-form')).toBeTruthy())
    fireEvent.change(screen.getByTestId('ae-chatter-input'), { target: { value: 'À roter' } })
    fireEvent.click(screen.getByTestId('ae-chatter-submit'))
    await waitFor(() => expect(mocks.postNote).toHaveBeenCalledWith('ad', 'ad-7', 'À roter'))
    // Recharge après post.
    expect(mocks.timeline).toHaveBeenCalledTimes(2)
  })
})
