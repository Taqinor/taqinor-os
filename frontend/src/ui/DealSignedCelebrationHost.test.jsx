import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import DealSignedCelebrationHost from './DealSignedCelebrationHost'
import { annoncerAffaireSignee, effacerAffaireSignee } from './dealSignedBus'
import { PARTY_ID } from './celebrate'

// La fête est rendue par un hôte GLOBAL dans document.body (hors de tout
// dialogue), au-dessus des modales, et disparaît à la fermeture.

function mockReduced() {
  window.matchMedia = vi.fn().mockReturnValue({
    matches: true, addEventListener: () => {}, removeEventListener: () => {},
  })
}

afterEach(() => {
  act(() => effacerAffaireSignee())
  cleanup()
  document.getElementById(PARTY_ID)?.remove()
  vi.restoreAllMocks()
})

describe('DealSignedCelebrationHost', () => {
  it('ne rend rien tant que rien n’est annoncé', () => {
    mockReduced()
    render(<DealSignedCelebrationHost />)
    expect(screen.queryByTestId('deal-signed-host')).toBeNull()
  })

  it('rend la fête dans document.body à l’annonce, puis la retire à la fermeture', async () => {
    mockReduced()
    const { container } = render(<DealSignedCelebrationHost />)
    act(() => annoncerAffaireSignee({ reference: 'DEV-0042', montantTtc: 150000, kwc: 7.1 }))
    const host = screen.getByTestId('deal-signed-host')
    expect(host.parentElement).toBe(document.body)
    expect(container.contains(host)).toBe(false)
    expect(host.className).toMatch(/z-\[var\(--z-toast\)\]/)
    expect(host.className).toMatch(/pointer-events-auto/)
    expect(screen.getByText(/DEV-0042/)).toBeInTheDocument()

    await userEvent.keyboard('{Escape}')
    expect(screen.queryByTestId('deal-signed-host')).toBeNull()
  })
})
