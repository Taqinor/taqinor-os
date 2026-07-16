import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { axe } from 'vitest-axe'
import { Button, buttonVariants } from './Button'
import { IconButton } from './IconButton'
import { Plus } from 'lucide-react'

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

  // ── G125 : six états + press tactile + libellés d'icônes ──────────────────
  describe('G125 — six états pilotés par tokens', () => {
    it('expose les états default/hover/focus-visible/active/disabled via les classes', () => {
      const cls = buttonVariants({})
      // hover et active sont distincts (default ≠ hover ≠ active)
      expect(cls).toMatch(/hover:bg-primary\/90/)
      expect(cls).toMatch(/active:bg-primary\/80/)
      // focus-visible piloté par la classe .focus-ring (VX123)
      expect(cls).toMatch(/focus-ring/)
      // disabled atténué et non cliquable
      expect(cls).toMatch(/disabled:opacity-50/)
      expect(cls).toMatch(/disabled:pointer-events-none/)
    })

    it('réserve le press tactile au pointeur fin via @media (hover:hover)', () => {
      const cls = buttonVariants({})
      expect(cls).toContain('[@media(hover:hover)]:active:scale-[0.97]')
      // timing ~150 ms cubic-bezier(0.23,1,0.32,1)
      expect(cls).toContain('duration-150')
      expect(cls).toContain('cubic-bezier(0.23,1,0.32,1)')
    })

    it('marque visuellement l’état loading (aria-busy + désactivé)', () => {
      render(<Button loading>Chargement</Button>)
      const btn = screen.getByRole('button', { name: /Chargement/ })
      expect(btn).toHaveAttribute('aria-busy', 'true')
      expect(btn).toBeDisabled()
    })
  })

  describe('G125 — IconButton étiqueté', () => {
    it('un bouton à icône seule porte un aria-label depuis `label`', () => {
      render(<IconButton label="Ajouter"><Plus /></IconButton>)
      expect(screen.getByRole('button', { name: 'Ajouter' })).toBeInTheDocument()
    })

    it('retombe sur un aria-label non vide si `label` manque', () => {
      render(<IconButton><Plus /></IconButton>)
      const btn = screen.getByRole('button')
      expect(btn.getAttribute('aria-label')).toBeTruthy()
    })

    it("n'a aucune violation d'accessibilité (bouton-icône)", async () => {
      const { container } = render(<IconButton label="Ajouter"><Plus /></IconButton>)
      const results = await axe(container)
      expect(results.violations).toEqual([])
    })
  })
})
