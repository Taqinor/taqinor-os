// LW32 — un seul Avatar (ui/Avatar tokenisé) + couleur stable par responsable
// via --owner-color-{1..10}. On ne rouvre pas le Popover ici (Radix rend le
// Trigger inconditionnellement, seul le Content est portalé/conditionnel) :
// il suffit d'inspecter l'avatar du déclencheur pour vérifier le hook DOM
// `.ap-trigger` et la couleur par owner.
import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'
import AssigneePicker from './AssigneePicker'

const USERS = [
  { id: 11, username: 'Reda Kasri', avatar_url: null },
  { id: 42, username: 'Sami Alami', avatar_url: null },
]

describe('AssigneePicker (LW32)', () => {
  it('garde les hooks DOM stables .ap-trigger / .ap-name (contrat e2e)', () => {
    const { container } = render(
      <AssigneePicker users={USERS} value={11} onChange={() => {}} />,
    )
    expect(container.querySelector('.ap-trigger')).toBeInTheDocument()
    expect(container.querySelector('.ap-name')).toHaveTextContent('Reda Kasri')
  })

  it('ne rend plus components/Avatar : le fallback vient de ui/Avatar (initiales, pas de <img> sans src)', () => {
    const { container } = render(
      <AssigneePicker users={USERS} value={11} onChange={() => {}} />,
    )
    // ui/Avatar : AvatarFallback rendu tant qu'aucune image ne charge — pas
    // d'`<img>` posé quand `avatar_url` est vide (l'ancien Avatar maison
    // rendait toujours un <span> ou un <img>, jamais les deux primitives
    // Radix distinctes).
    expect(container.querySelector('.ap-trigger img')).not.toBeInTheDocument()
    expect(container.querySelector('.ap-trigger').textContent).toMatch(/RK/)
  })

  it('deux responsables différents obtiennent deux couleurs --owner-color-N stables (hash sur l’ID)', () => {
    const { container: c1 } = render(
      <AssigneePicker users={USERS} value={11} onChange={() => {}} />,
    )
    const { container: c2 } = render(
      <AssigneePicker users={USERS} value={42} onChange={() => {}} />,
    )
    const color1 = c1.querySelector('.ap-trigger .ap-avatar-fallback')?.style.color
    const color2 = c2.querySelector('.ap-trigger .ap-avatar-fallback')?.style.color
    expect(color1).toMatch(/^var\(--owner-color-\d+\)$/)
    expect(color2).toMatch(/^var\(--owner-color-\d+\)$/)
    expect(color1).not.toBe(color2)

    // Stabilité : re-rendre le même owner (id=11) redonne EXACTEMENT la même
    // variable de couleur (pas un hasard de rendu).
    const { container: c1bis } = render(
      <AssigneePicker users={USERS} value={11} onChange={() => {}} />,
    )
    const color1bis = c1bis.querySelector('.ap-trigger .ap-avatar-fallback')?.style.color
    expect(color1bis).toBe(color1)
  })

  it('« Non assigné » retombe sur --muted-foreground (pas de owner-color pour id=null)', () => {
    const { container } = render(
      <AssigneePicker users={USERS} value="" onChange={() => {}} />,
    )
    const fallback = container.querySelector('.ap-trigger .ap-avatar-fallback')
    expect(fallback?.style.color).toBe('var(--muted-foreground)')
  })
})
