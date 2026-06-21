import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { DatePicker } from './DatePicker'
import { TimePicker } from './TimePicker'

/* G128 — DatePicker / TimePicker tokenisés (clair/sombre) + hauteurs alignées
   sur les tokens de densité. On vérifie le rendu et l'usage des tokens plutôt
   que des couleurs codées en dur. */
describe('G128 — DatePicker tokenisé', () => {
  it('rend le déclencheur avec les tokens de surface/texte', () => {
    render(<DatePicker value="2026-06-21" clearable={false} />)
    const trigger = screen.getByRole('button')
    expect(trigger.className).toContain('bg-card')
    expect(trigger.className).toContain('text-foreground')
    // aucune couleur codée en dur
    expect(trigger.className).not.toMatch(/text-white|bg-nuit|bg-white/)
  })

  it('aligne la hauteur des cellules sur le token de densité une fois ouvert', async () => {
    render(<DatePicker value={null} />)
    const trigger = screen.getByRole('button')
    trigger.click()
    const grid = await screen.findByRole('grid')
    const cell = grid.querySelector('[role="gridcell"]')
    expect(cell).not.toBeNull()
    expect(cell.className).toContain('h-[var(--control-h-sm)]')
  })
})

describe('G128 — TimePicker tokenisé', () => {
  it('rend le champ avec les tokens de surface et la hauteur de contrôle', () => {
    const { container } = render(<TimePicker value="" />)
    const field = container.querySelector('.bg-card')
    expect(field).not.toBeNull()
    expect(field.className).toContain('h-[var(--control-h)]')
    expect(field.className).not.toMatch(/text-white|bg-nuit|bg-white/)
  })
})
