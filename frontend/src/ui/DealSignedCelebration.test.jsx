import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import DealSignedCelebration from './DealSignedCelebration'

// VX155 — la carte de victoire du devis SIGNÉ : montant + kWc réels, CO₂
// dérivé, et — sous prefers-reduced-motion — la MÊME carte, seulement SANS
// mouvement (jamais moins d'information, jamais un repli silencieux).

function mockMatchMedia(reduced) {
  window.matchMedia = vi.fn().mockImplementation((query) => ({
    matches: reduced && query.includes('prefers-reduced-motion'),
    media: query,
    addEventListener: () => {},
    removeEventListener: () => {},
  }))
}

afterEach(() => {
  cleanup()
  document.getElementById('vx40-deal-signed-burst')?.remove()
  vi.restoreAllMocks()
})

describe('VX155 — DealSignedCelebration', () => {
  it('affiche le montant et le kWc réels transmis par l’appelant', () => {
    mockMatchMedia(false)
    render(
      <DealSignedCelebration
        open reference="DEV-0042" montantTtc={150000} kwc={7.1}
        onClose={() => {}}
      />,
    )
    expect(screen.getByText(/DEV-0042/)).toBeInTheDocument()
    expect(screen.getByText(/150\s000,00 MAD/)).toBeInTheDocument()
    expect(screen.getByText(/7[.,]1 kWc/)).toBeInTheDocument()
    expect(screen.getByText(/t CO₂ évitées\/an/)).toBeInTheDocument()
  })

  it('omet la ligne kWc/CO₂ quand le kWc n’est pas connu (jamais un chiffre inventé)', () => {
    mockMatchMedia(false)
    render(
      <DealSignedCelebration open reference="DEV-0043" montantTtc={80000} kwc={null} onClose={() => {}} />,
    )
    expect(screen.queryByText(/kWc/)).not.toBeInTheDocument()
    expect(screen.queryByText(/CO₂/)).not.toBeInTheDocument()
  })

  it('ne rend rien quand open=false', () => {
    mockMatchMedia(false)
    render(<DealSignedCelebration open={false} montantTtc={1000} onClose={() => {}} />)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('reduced-motion : la carte reste affichée, SANS mouvement (pas de burst, TaqinorMark statique)', () => {
    mockMatchMedia(true)
    render(
      <DealSignedCelebration open reference="DEV-0044" montantTtc={99000} kwc={5} onClose={() => {}} />,
    )
    // La carte est là (jamais un simple toast de repli) :
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(screen.getByText(/99\s000,00 MAD/)).toBeInTheDocument()
    // … mais sans mouvement : aucun burst posé, TaqinorMark non animé.
    expect(document.getElementById('vx40-deal-signed-burst')).toBeFalsy()
    expect(document.querySelector('.taqinor-mark--animate')).toBeFalsy()
  })

  it('le bouton « Continuer » appelle onClose', async () => {
    mockMatchMedia(false)
    const onClose = vi.fn()
    render(<DealSignedCelebration open montantTtc={1000} onClose={onClose} />)
    await userEvent.click(screen.getByRole('button', { name: 'Continuer' }))
    expect(onClose).toHaveBeenCalled()
  })
})
