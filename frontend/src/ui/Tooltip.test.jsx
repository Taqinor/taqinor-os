import { describe, it, expect, beforeAll } from 'vitest'
import { render, screen } from '@testing-library/react'
import {
  TooltipProvider,
  Tooltip,
  TooltipTrigger,
  TooltipContent,
} from './Tooltip'

// La flèche Radix (TooltipPrimitive.Arrow) mesure sa taille via ResizeObserver,
// absent de jsdom : on fournit un stub minimal pour ce fichier.
beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

/* G124 — Tooltip thémable. On vérifie que le contenu est piloté par les tokens
   `popover` / `popover-foreground` (donc s'adapte clair ↔ sombre) et NON par la
   couleur sombre codée en dur (`bg-nuit` / `text-white`) d'avant. */
describe('Tooltip (primitif UI, G124)', () => {
  function openTooltip() {
    return render(
      <TooltipProvider>
        <Tooltip defaultOpen>
          <TooltipTrigger>Aide</TooltipTrigger>
          <TooltipContent>Texte d’aide</TooltipContent>
        </Tooltip>
      </TooltipProvider>,
    )
  }

  it('rend le contenu du tooltip ouvert', () => {
    openTooltip()
    // Radix peut rendre plusieurs copies (visible + lecteur d'écran).
    expect(screen.getAllByText('Texte d’aide').length).toBeGreaterThan(0)
  })

  it('utilise les tokens popover et non les couleurs codées en dur', () => {
    const { container } = openTooltip()
    const content = container.ownerDocument.body.querySelector(
      '[data-radix-popper-content-wrapper] [class*="bg-popover"]',
    )
    expect(content).not.toBeNull()
    expect(content.className).toContain('bg-popover')
    expect(content.className).toContain('text-popover-foreground')
    expect(content.className).not.toContain('bg-nuit')
    expect(content.className).not.toContain('text-white')
  })
})
