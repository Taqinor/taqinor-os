import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

vi.mock('../api/recordsApi', () => ({
  default: {
    getMyFollow: vi.fn(() => Promise.resolve({ data: [] })),
    follow: vi.fn(() => Promise.resolve({ data: { id: 99 } })),
    unfollow: vi.fn(() => Promise.resolve({ data: null })),
  },
}))

import recordsApi from '../api/recordsApi'
import FollowToggle from './FollowToggle'

describe('FollowToggle (WIR72)', () => {
  it('affiche « Suivre » quand l\'utilisateur ne suit pas encore', async () => {
    render(<FollowToggle model="crm.lead" id={1} />)
    const btn = await screen.findByRole('button', { name: /Suivre/ })
    expect(btn).toHaveAttribute('aria-pressed', 'false')
  })

  it('suivre appelle records.follow puis bascule vers « Ne plus suivre »', async () => {
    render(<FollowToggle model="crm.lead" id={1} />)
    const btn = await screen.findByRole('button', { name: /Suivre/ })
    fireEvent.click(btn)
    await waitFor(() =>
      expect(recordsApi.follow).toHaveBeenCalledWith('crm.lead', 1))
    expect(await screen.findByRole('button', { name: /Ne plus suivre/ }))
      .toHaveAttribute('aria-pressed', 'true')
  })

  it('détecte un abonnement existant (mine=1) et le retire', async () => {
    recordsApi.getMyFollow.mockResolvedValueOnce({ data: [{ id: 42 }] })
    render(<FollowToggle model="sav.ticket" id={5} />)
    const btn = await screen.findByRole('button', { name: /Ne plus suivre/ })
    fireEvent.click(btn)
    await waitFor(() =>
      expect(recordsApi.unfollow).toHaveBeenCalledWith(42))
  })

  it('une cible non abonnable (400) désactive le bouton sans casser l\'écran', async () => {
    recordsApi.getMyFollow.mockRejectedValueOnce(new Error('400'))
    render(<FollowToggle model="crm.lead" id={1} />)
    const btn = await screen.findByRole('button')
    expect(btn).toBeDisabled()
  })
})
