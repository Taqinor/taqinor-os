import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { FadeSwap } from './FadeSwap'

/* VX132 — <FadeSwap> : transition croisée générique squelette → contenu
   (le passage était un swap SEC partout jusqu'ici — pas de crossfade). */
describe('FadeSwap (VX132)', () => {
  it('loading=true : le squelette est visible, le contenu est masqué (aria-hidden)', () => {
    render(
      <FadeSwap loading skeleton={<p>Squelette</p>}>
        <p>Contenu réel</p>
      </FadeSwap>,
    )
    const skeletonWrap = screen.getByText('Squelette').parentElement
    const contentWrap = screen.getByText('Contenu réel').parentElement
    expect(skeletonWrap).toHaveAttribute('aria-hidden', 'false')
    expect(contentWrap).toHaveAttribute('aria-hidden', 'true')
    expect(contentWrap.className).toMatch(/opacity-0/)
    expect(skeletonWrap.className).toMatch(/opacity-100/)
  })

  it('loading=false : le contenu est visible, le squelette est masqué', () => {
    render(
      <FadeSwap loading={false} skeleton={<p>Squelette</p>}>
        <p>Contenu réel</p>
      </FadeSwap>,
    )
    const skeletonWrap = screen.getByText('Squelette').parentElement
    const contentWrap = screen.getByText('Contenu réel').parentElement
    expect(contentWrap).toHaveAttribute('aria-hidden', 'false')
    expect(skeletonWrap).toHaveAttribute('aria-hidden', 'true')
    expect(contentWrap.className).toMatch(/opacity-100/)
    expect(skeletonWrap.className).toMatch(/opacity-0/)
  })

  it('les deux calques transitionnent sur --motion-base (pas une valeur fixe)', () => {
    render(
      <FadeSwap loading skeleton={<p>Squelette</p>}>
        <p>Contenu réel</p>
      </FadeSwap>,
    )
    const skeletonWrap = screen.getByText('Squelette').parentElement
    expect(skeletonWrap.className).toMatch(/duration-\[var\(--motion-base\)\]/)
  })
})
