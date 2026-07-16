import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { axe } from 'vitest-axe'
import { FloatingActionButton } from './FloatingActionButton'
import { Camera } from 'lucide-react'

/* VX42 — Bouton d'action flottant : accessible (label = nom accessible),
   déclenche `onClick`, et porte la classe `.fab-button` qui pilote sa
   position fixe + safe-area en CSS (masqué sur bureau, visible ≤ 768 px). */
describe('FloatingActionButton (VX42)', () => {
  it('rend un bouton avec le label comme nom accessible', () => {
    render(<FloatingActionButton label="Photo rapide" icon={<Camera />} onClick={() => {}} />)
    expect(screen.getByRole('button', { name: 'Photo rapide' })).toBeInTheDocument()
  })

  it('déclenche onClick au tap', () => {
    const onClick = vi.fn()
    render(<FloatingActionButton label="Nouveau lead" icon={<Camera />} onClick={onClick} />)
    fireEvent.click(screen.getByRole('button', { name: 'Nouveau lead' }))
    expect(onClick).toHaveBeenCalledTimes(1)
  })

  it('porte la classe fab-button (position fixe + safe-area pilotées en CSS)', () => {
    render(<FloatingActionButton label="Photo rapide" icon={<Camera />} onClick={() => {}} />)
    expect(screen.getByRole('button', { name: 'Photo rapide' })).toHaveClass('fab-button')
  })

  it('accepte une className additionnelle sans perdre fab-button', () => {
    render(<FloatingActionButton label="Photo rapide" icon={<Camera />} onClick={() => {}} className="extra" />)
    const btn = screen.getByRole('button', { name: 'Photo rapide' })
    expect(btn).toHaveClass('fab-button')
    expect(btn).toHaveClass('extra')
  })

  it("aucune violation d'accessibilité", async () => {
    const { container } = render(
      <FloatingActionButton label="Photo rapide" icon={<Camera aria-hidden="true" />} onClick={() => {}} />,
    )
    const results = await axe(container)
    expect(results.violations).toEqual([])
  })
})
