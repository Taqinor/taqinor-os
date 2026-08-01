import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import EnveloppeL from './EnveloppeL'
import {
  L_REFERENCE,
  validerL,
  contourL,
  empriseAile,
  bandeL,
  modulesParBande,
  perteDuDecoupage,
} from './EnveloppeL.geometrie'
import { aireM2, contourSeCroise } from './repere'

/* AOF91 — le « L » se saisit d'un seul tenant. Ce qui est prouvé ici : un
   CONTOUR UNIQUE à six sommets (jamais deux rectangles), une bande qui traverse
   la jonction sans coupure, et la perte sèche du découpage, CHIFFRÉE. */

// Aile plus creuse que le défaut : les restes ne tombent plus juste, la perte apparaît.
const AILE_PROFONDE = { ...L_REFERENCE, aileProfondeurM: 8.82 }

describe('géométrie du L (AOF91)', () => {
  it('produit UN contour de six sommets, jamais deux rectangles', () => {
    const c = contourL(AILE_PROFONDE)
    expect(c).toHaveLength(6)
    expect(contourSeCroise(c)).toBe(false)
    // Aire = barre + aile, sans double compte ni trou.
    expect(aireM2(c)).toBeCloseTo(51.1 * 25.62 + 18 * 8.82, 6)
    expect(c[0]).toEqual({ x: 0, y: 0 })
    expect(c[2].x).toBeCloseTo(51.1, 9)
    expect(c[2].y).toBeCloseTo(34.44, 9)
    expect(c[4].x).toBeCloseTo(33.1, 9)
    expect(c[4].y).toBeCloseTo(25.62, 9)
  })

  it('place l’aile au bon coin, contour toujours d’un seul tenant', () => {
    for (const coin of ['NE', 'NO', 'SE', 'SO']) {
      const c = contourL({ ...AILE_PROFONDE, coin })
      expect(c).toHaveLength(6)
      expect(contourSeCroise(c)).toBe(false)
      expect(aireM2(c)).toBeCloseTo(51.1 * 25.62 + 18 * 8.82, 6)
      expect(Math.min(...c.map((p) => p.y))).toBeCloseTo(0, 9)
    }
    expect(empriseAile({ ...AILE_PROFONDE, coin: 'NE' }).debut).toBeCloseTo(33.1, 9)
    expect(empriseAile({ ...AILE_PROFONDE, coin: 'NO' })).toEqual({ debut: 0, fin: 18 })
  })

  it('sous l’aile, la bande descend d’un seul tenant de la barre dans l’aile', () => {
    const sous = bandeL(AILE_PROFONDE, 42)
    expect(sous.sousAile).toBe(true)
    expect(sous.ymax - sous.ymin).toBeCloseTo(25.62 + 8.82, 6)

    const hors = bandeL(AILE_PROFONDE, 10)
    expect(hors.sousAile).toBe(false)
    expect(hors.ymax - hors.ymin).toBeCloseTo(25.62, 6)

    // Au sud, la barre est décalée mais la bande sous l'aile reste continue.
    const sud = bandeL({ ...AILE_PROFONDE, coin: 'SO' }, 9)
    expect(sud.ymin).toBeCloseTo(0, 9)
    expect(sud.ymax).toBeCloseTo(34.44, 6)
    expect(bandeL({ ...AILE_PROFONDE, coin: 'SO' }, 40).ymin).toBeCloseTo(8.82, 6)
  })

  it('CHIFFRE la perte sèche du découpage en deux rectangles', () => {
    expect(modulesParBande(34.44, 4.7, 0.35)).toBe(7)
    expect(modulesParBande(25.62, 4.7, 0.35)).toBe(5)
    expect(modulesParBande(8.82, 4.7, 0.35)).toBe(1)

    const p = perteDuDecoupage(AILE_PROFONDE, { moduleM: 4.7, riveM: 0.35, pasM: 1.134 })
    expect(p.continu).toBe(7)
    expect(p.decoupe).toBe(6) // 5 + 1 : chaque morceau reprend ses rives et perd son reste
    expect(p.parBande).toBe(1)
    expect(p.bandesSousAile).toBe(15)
    expect(p.perte).toBe(15)
    // Le découpage n'est JAMAIS meilleur que le contour continu.
    expect(p.continu).toBeGreaterThanOrEqual(p.decoupe)
  })

  it('refuse une saisie incomplète ou qui n’est plus un L', () => {
    expect(validerL({}).valide).toBe(false)
    expect(validerL({}).motifs).toHaveLength(2)
    expect(validerL({ barreLongueurM: 51.1, barreProfondeurM: 25.62 }).motifs[0]).toMatch(
      /Aile incomplète/,
    )
    expect(
      validerL({ barreLongueurM: 20, barreProfondeurM: 10, aileLongueurM: 20, aileProfondeurM: 5 })
        .motifs[0],
    ).toMatch(/c’est un rectangle, pas un L/)
    expect(validerL(AILE_PROFONDE)).toEqual({ valide: true, motifs: [] })
  })
})

describe('EnveloppeL — écran (AOF91)', () => {
  it('rend un polygone unique et affiche la règle du seul tenant', () => {
    const { container } = render(<EnveloppeL valeurInitiale={AILE_PROFONDE} />)
    expect(container.querySelectorAll('polygon')).toHaveLength(1)
    expect(container.querySelector('[data-ao-l-sommets]').dataset.aoLSommets).toBe('6')
    expect(container.querySelector('[data-ao-l-regle]').textContent).toMatch(
      /Jamais deux rectangles/,
    )
    expect(container.querySelector('[data-ao-l-perte]').dataset.aoLPerte).toBe('15')
    expect(container.querySelector('[data-ao-l-bande="traversante"]')).not.toBeNull()
  })

  it('remonte le contour à la validation, et refuse une aile aussi longue que la barre', async () => {
    const user = userEvent.setup()
    const onValider = vi.fn()
    render(<EnveloppeL valeurInitiale={AILE_PROFONDE} onValider={onValider} />)

    await user.click(screen.getByRole('button', { name: /Valider l’enveloppe en L/ }))
    const rendu = onValider.mock.calls[0][0]
    expect(rendu.sommets).toHaveLength(6)
    expect(rendu.aireM2).toBeCloseTo(51.1 * 25.62 + 18 * 8.82, 6)

    onValider.mockClear()
    await user.clear(screen.getByLabelText('Aile — longueur (m)'))
    await user.type(screen.getByLabelText('Aile — longueur (m)'), '51.1')
    await user.click(screen.getByRole('button', { name: /Valider l’enveloppe en L/ }))
    expect(onValider).not.toHaveBeenCalled()
    expect(screen.getByRole('alert').textContent).toMatch(/c’est un rectangle, pas un L/)
  })
})
