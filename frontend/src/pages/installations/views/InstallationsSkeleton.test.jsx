import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'
import { axe } from 'vitest-axe'
import InstallationsSkeleton from './InstallationsSkeleton'

/* J143 — Squelette de chargement des chantiers, calqué sur la forme du contenu
   (colonnes kanban / lignes de liste) pour ne jamais provoquer de saut de mise
   en page quand les vrais chantiers arrivent. Entièrement masqué aux lecteurs
   d'écran (aria-hidden) — le libellé « Chargement » vit dans la page. */
describe('InstallationsSkeleton (J143)', () => {
  it('est masqué aux lecteurs d’écran (aria-hidden)', () => {
    const { container } = render(<InstallationsSkeleton view="kanban" />)
    expect(container.firstChild).toHaveAttribute('aria-hidden', 'true')
  })

  it('vue kanban : rend plusieurs colonnes-squelette', () => {
    const { container } = render(<InstallationsSkeleton view="kanban" />)
    expect(
      container.querySelectorAll('.kb-col').length,
    ).toBeGreaterThan(1)
  })

  it('vue liste : rend des lignes-squelette dans un tableau', () => {
    const { container } = render(<InstallationsSkeleton view="liste" />)
    // au moins une ligne-squelette (tr aria-hidden) dans un tbody
    expect(container.querySelector('table')).toBeTruthy()
    expect(container.querySelectorAll('tbody tr').length).toBeGreaterThan(1)
  })

  it('vue calendrier : rend une grille-squelette', () => {
    const { container } = render(<InstallationsSkeleton view="calendrier" />)
    expect(container.querySelector('.cal-grid')).toBeTruthy()
  })

  it('vue inconnue : repli sur la forme liste sans planter', () => {
    const { container } = render(<InstallationsSkeleton view="???" />)
    expect(container.firstChild).toHaveAttribute('aria-hidden', 'true')
  })

  it("aucune violation d'accessibilité", async () => {
    const { container } = render(<InstallationsSkeleton view="kanban" />)
    const results = await axe(container)
    expect(results.violations).toEqual([])
  })
})
