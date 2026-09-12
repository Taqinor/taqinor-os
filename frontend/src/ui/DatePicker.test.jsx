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

/* NTI18N6 — une date (jj/mm/aaaa) reste lisible de gauche à droite même en
   contexte RTL (mêmes chiffres, même convention que NumberInput/
   CurrencyInput) : le libellé affiché ET la grille du calendrier portent
   `dir="ltr"` explicite, indépendamment de l'ancêtre RTL. */
describe('NTI18N6 — DatePicker, chiffres LTR même en contexte RTL', () => {
  it('le libellé de date affiché porte dir="ltr"', () => {
    render(
      <div dir="rtl">
        <DatePicker value="2026-06-21" clearable={false} />
      </div>,
    )
    const trigger = screen.getByRole('button')
    const label = trigger.querySelector('span')
    expect(label).toHaveAttribute('dir', 'ltr')
  })

  it('la grille calendrier ouverte porte dir="ltr"', async () => {
    render(
      <div dir="rtl">
        <DatePicker value={null} />
      </div>,
    )
    screen.getByRole('button').click()
    const grid = await screen.findByRole('grid')
    // `dir="ltr"` est posé sur le conteneur PARENT immédiat de la grille
    // (voir DatePicker.jsx `CalendarGrid`), pas sur le `role="grid"` lui-même.
    expect(grid.closest('[dir="ltr"]')).not.toBeNull()
  })
})
