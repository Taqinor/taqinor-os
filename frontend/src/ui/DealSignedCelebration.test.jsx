import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ReactReduxContext } from 'react-redux'
import DealSignedCelebration from './DealSignedCelebration'
import { PARTY_ID } from './celebrate'

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
  document.getElementById(PARTY_ID)?.remove()
  vi.restoreAllMocks()
})

describe('VX155 — DealSignedCelebration', () => {
  it('affiche le montant et le kWc réels transmis par l’appelant', async () => {
    mockMatchMedia(false)
    render(
      <DealSignedCelebration
        open reference="DEV-0042" montantTtc={150000} kwc={7.1}
        onClose={() => {}}
      />,
    )
    expect(screen.getByText(/DEV-0042/)).toBeInTheDocument()
    expect(await screen.findByText(/150\s000,00 MAD/, {}, { timeout: 5000 })).toBeInTheDocument()
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

  it('reduced-motion : la carte reste affichée, SANS mouvement (pas de fête, TaqinorMark statique)', () => {
    mockMatchMedia(true)
    render(
      <DealSignedCelebration open reference="DEV-0044" montantTtc={99000} kwc={5} onClose={() => {}} />,
    )
    // La carte est là (jamais un simple toast de repli) :
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(screen.getByText(/99\s000,00 MAD/)).toBeInTheDocument()
    // … mais sans mouvement : aucune fête posée, TaqinorMark non animé.
    expect(document.getElementById(PARTY_ID)).toBeFalsy()
    expect(document.querySelector('.taqinor-mark--animate')).toBeFalsy()
  })

  it('le bouton « Continuer » appelle onClose', async () => {
    mockMatchMedia(false)
    const onClose = vi.fn()
    render(<DealSignedCelebration open montantTtc={1000} onClose={onClose} />)
    await userEvent.click(screen.getByRole('button', { name: 'Continuer' }))
    expect(onClose).toHaveBeenCalled()
  })

  it('acclame la vendeuse connectée par son prénom', () => {
    mockMatchMedia(true)
    const store = { getState: () => ({ auth: { user: { first_name: 'Meryem' } } }), subscribe: () => () => {} }
    render(
      <ReactReduxContext.Provider value={{ store }}>
        <DealSignedCelebration open montantTtc={1000} onClose={() => {}} />
      </ReactReduxContext.Provider>,
    )
    expect(screen.getByRole('heading', { name: 'Bravo Meryem !' })).toBeInTheDocument()
  })

  it('le montant défile jusqu’au TTC réel et la fête est lancée', async () => {
    mockMatchMedia(false)
    render(<DealSignedCelebration open montantTtc={150000} onClose={() => {}} />)
    expect(document.getElementById(PARTY_ID)).toBeTruthy()
    expect(await screen.findByText(/150\s000,00 MAD/, {}, { timeout: 5000 })).toBeInTheDocument()
  })

  it('Échap ferme la fête et la scène est retirée', async () => {
    mockMatchMedia(false)
    const onClose = vi.fn()
    const { unmount } = render(<DealSignedCelebration open montantTtc={1000} onClose={onClose} />)
    await userEvent.keyboard('{Escape}')
    expect(onClose).toHaveBeenCalled()
    unmount()
    expect(document.getElementById(PARTY_ID)).toBeFalsy()
  })
})
