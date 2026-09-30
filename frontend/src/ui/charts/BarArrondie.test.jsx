import { describe, it, expect, vi } from 'vitest'
import { cloneElement } from 'react'
import { render } from '@testing-library/react'

// En jsdom, ResponsiveContainer n'a pas de taille : on le remplace par un
// conteneur à dimensions FIXES pour que recharts dessine vraiment le SVG.
vi.mock('recharts', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    ResponsiveContainer: ({ children, height }) => cloneElement(children, {
      width: 400, height: typeof height === 'number' ? height : 200,
    }),
  }
})

import { BarArrondie } from './BarArrondie.jsx'

// prefers-reduced-motion → durée d'animation 0 : barres à leur taille finale
// dès le premier rendu (sinon elles partent de 0 px).
window.matchMedia = (q) => ({
  matches: true, media: q, onchange: null,
  addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {}, dispatchEvent() { return false },
})

/* ERR-QAH-STOCK-GRAPHES-PILOTAGE-VIDES — les axes étaient enveloppés dans un
   fragment `<>` : recharts 2 (react-is 18) ne l'aplatit pas sous React 19 →
   axes ignorés, barres horizontales à y négatif, aucun libellé. */
describe('BarArrondie — axes rendus (ERR-QAH-STOCK-GRAPHES-PILOTAGE-VIDES)', () => {
  const data = [
    { label: 'Onduleur', value: 12 },
    { label: 'Panneau', value: 20 },
    { label: 'Câble', value: 8 },
    { label: 'Batterie', value: 12 },
  ]

  it('barres horizontales : un libellé par catégorie et des barres dans le cadre', () => {
    const { container } = render(
      <BarArrondie data={data} layout="vertical" categoryKey="label" dataKey="value" />,
    )
    const ticks = [...container.querySelectorAll('.recharts-yAxis .recharts-cartesian-axis-tick text')]
      .map((t) => t.textContent)
    expect(ticks).toEqual(['Onduleur', 'Panneau', 'Câble', 'Batterie'])
    const bars = [...container.querySelectorAll('.recharts-bar-rectangle path')]
    expect(bars).toHaveLength(4)
    for (const b of bars) {
      expect(Number(b.getAttribute('y'))).toBeGreaterThanOrEqual(0)
      expect(Number(b.getAttribute('x'))).toBeGreaterThan(0) // décalé par l'axe des catégories
    }
  })

  it('barres verticales : axe des catégories rendu', () => {
    const { container } = render(<BarArrondie data={data} />)
    const ticks = [...container.querySelectorAll('.recharts-xAxis .recharts-cartesian-axis-tick text')]
      .map((t) => t.textContent)
    expect(ticks).toEqual(['Onduleur', 'Panneau', 'Câble', 'Batterie'])
  })

  it('allowDecimals : une moyenne < 1 occupe le cadre au lieu d\'être écrasée', () => {
    const { container } = render(
      <BarArrondie data={[{ label: 'P', value: 0.17 }]} layout="vertical" allowDecimals />,
    )
    const bar = container.querySelector('.recharts-bar-rectangle path')
    expect(bar).not.toBeNull()
    expect(Number(bar.getAttribute('width'))).toBeGreaterThan(100)
  })
})
