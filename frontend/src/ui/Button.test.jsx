import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { axe } from 'vitest-axe'
import { Button } from './Button'

/* Tests d'INTERACTION + ACCESSIBILITÉ du primitif Button (RTL + axe). Vérifie le
   comportement visible (rôle, clic, état chargement), pas l'implémentation. */
describe('Button (primitif UI)', () => {
  it('rend son libellé et déclenche onClick', async () => {
    const onClick = vi.fn()
    render(<Button onClick={onClick}>Enregistrer</Button>)
    await userEvent.click(screen.getByRole('button', { name: 'Enregistrer' }))
    expect(onClick).toHaveBeenCalledTimes(1)
  })

  it('est désactivé et non cliquable pendant le chargement (aria-busy)', async () => {
    const onClick = vi.fn()
    render(
      <Button loading onClick={onClick}>
        Envoi…
      </Button>,
    )
    const btn = screen.getByRole('button', { name: /Envoi/ })
    expect(btn).toBeDisabled()
    expect(btn).toHaveAttribute('aria-busy', 'true')
    await userEvent.click(btn)
    expect(onClick).not.toHaveBeenCalled()
  })

  it("n'a aucune violation d'accessibilité détectable", async () => {
    const { container } = render(<Button>Valider le devis</Button>)
    const results = await axe(container)
    expect(results.violations).toEqual([])
  })
})
