import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'
import { axe } from 'vitest-axe'
import {
  Skeleton,
  SkeletonText,
  SkeletonLine,
  SkeletonCard,
  SkeletonTableRow,
  SkeletonAvatar,
} from './Skeleton'

/* L153 — Variantes de squelette calquées sur la forme du contenu (ligne, carte,
   ligne de tableau, avatar). On vérifie qu'elles rendent du DOM masqué aux
   lecteurs d'écran (aria-hidden) et sans violation d'accessibilité. */
describe('Skeleton — variantes de mise en page (L153)', () => {
  it('le bloc de base est masqué aux lecteurs d’écran et porte le balayage shimmer (VX132)', () => {
    const { container } = render(<Skeleton />)
    const el = container.firstChild
    expect(el).toHaveAttribute('aria-hidden', 'true')
    // VX132 — pulse Tailwind par défaut remplacé par un balayage lumineux
    // directionnel (`.skeleton-shimmer`, tokens.css) ; se fige sous
    // reduced-motion via le garde global `*` d'index.css (pas de variant
    // motion-safe: dédié ici, cf. VX129 Progress).
    expect(el).toHaveClass('skeleton-shimmer')
  })

  it('SkeletonLine rend une seule ligne (hauteur de texte)', () => {
    const { container } = render(<SkeletonLine />)
    const el = container.firstChild
    expect(el).toHaveAttribute('aria-hidden', 'true')
    // une seule ligne, pas un conteneur multi-lignes
    expect(el.children.length).toBe(0)
  })

  it('SkeletonText rend le nombre de lignes demandé', () => {
    const { container } = render(<SkeletonText lines={4} />)
    // 4 lignes squelette dans le conteneur
    expect(container.firstChild.children.length).toBe(4)
  })

  it('SkeletonAvatar est rond', () => {
    const { container } = render(<SkeletonAvatar />)
    expect(container.firstChild).toHaveClass('rounded-full')
    expect(container.firstChild).toHaveAttribute('aria-hidden', 'true')
  })

  it('SkeletonCard contient des blocs (forme de carte)', () => {
    const { container } = render(<SkeletonCard />)
    const card = container.firstChild
    expect(card).toHaveAttribute('aria-hidden', 'true')
    // une carte non vide : au moins un bloc squelette interne
    expect(card.querySelectorAll('[aria-hidden="true"]').length).toBeGreaterThan(0)
  })

  it('SkeletonTableRow rend autant de cellules que `columns`', () => {
    const { container } = render(<SkeletonTableRow columns={5} />)
    const row = container.firstChild
    expect(row).toHaveAttribute('aria-hidden', 'true')
    // 5 cellules-squelette dans la ligne
    expect(row.children.length).toBe(5)
  })

  it('chaque variante accepte une className additionnelle', () => {
    const { container } = render(<SkeletonCard className="w-80" />)
    expect(container.firstChild).toHaveClass('w-80')
  })

  it("aucune violation d'accessibilité sur l'ensemble des variantes", async () => {
    const { container } = render(
      <div>
        <SkeletonLine />
        <SkeletonText lines={3} />
        <SkeletonAvatar />
        <SkeletonCard />
        <table>
          <tbody>
            <SkeletonTableRow columns={3} />
          </tbody>
        </table>
      </div>,
    )
    const results = await axe(container)
    expect(results.violations).toEqual([])
  })
})
