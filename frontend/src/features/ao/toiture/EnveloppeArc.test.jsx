import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import EnveloppeArc, {
  ARC_REFERENCE,
  validerArc,
  decouperArc,
  pasDePose,
  recouvrementEvite,
  rangeesProposees,
  rangeeACheval,
  cheminSecteur,
} from './EnveloppeArc'

/* AOF91 — l'arc du relevé de référence : R_ext 274,00 · largeur 10,90 (R_int
   263,10) · trois segments 20,55 + 23,00 + 23,60 séparés par deux murets de
   0,45, développé muret-à-muret 68,05 m.
   Ce qui est prouvé ici : le développé se retrouve au centimètre, AUCUNE rangée
   n'est proposée à cheval sur un muret, et un arc sans rayon ni largeur est
   refusé AVEC son motif (jamais accepté « en attendant »). */

describe('géométrie de l’arc (AOF91)', () => {
  it('découpe les 3 segments et redonne le développé 68,05 m', () => {
    const arc = decouperArc(ARC_REFERENCE)
    expect(arc.developpeTotal).toBeCloseTo(68.05, 6)
    expect(arc.rayonIntM).toBeCloseTo(263.1, 6)
    expect(arc.segments).toHaveLength(3)
    expect(arc.murets).toHaveLength(2)
    // Les murets sont AU RAS, entre deux segments consécutifs.
    expect(arc.murets[0].debut).toBeCloseTo(20.55, 6)
    expect(arc.murets[0].fin).toBeCloseTo(21.0, 6)
    expect(arc.segments[1].debut).toBeCloseTo(21.0, 6)
    expect(arc.segments[2].fin).toBeCloseTo(68.05, 6)
    // Chaque segment reprend ses PROPRES rives d'extrémité.
    expect(arc.segments[0].utileDebut).toBeCloseTo(0.35, 6)
    expect(arc.segments[0].utile).toBeCloseTo(20.55 - 0.7, 6)
    expect(arc.angleTotalRad).toBeCloseTo(68.05 / 274, 9)
  })

  it('corrige le pas de pose au rayon INTÉRIEUR (sinon les tables se recouvrent)', () => {
    const pas = pasDePose(1.134, 274, 263.1, 0)
    expect(pas).toBeGreaterThan(1.134)
    expect(pas).toBeCloseTo((1.134 * 274) / 263.1, 9)
    // ~4,7 cm de recouvrement évité par table — c'est ce qui coûte des modules.
    expect(recouvrementEvite(1.134, 274, 263.1, 0) * 100).toBeCloseTo(4.7, 1)
    // Plus on s'éloigne du bord intérieur, moins la correction est forte.
    expect(pasDePose(1.134, 274, 263.1, 10.9)).toBeCloseTo(1.134, 9)
  })

  it('ne propose JAMAIS une rangée à cheval sur un muret', () => {
    const { arc, rangees } = rangeesProposees(ARC_REFERENCE, 1.134)
    expect(rangees.length).toBeGreaterThan(0)
    expect(rangees.filter((r) => rangeeACheval(r, arc.murets))).toHaveLength(0)
    // Chaque rangée tient entre les rives de SON segment.
    for (const r of rangees) {
      const seg = arc.segments[r.segment]
      expect(r.debut).toBeGreaterThanOrEqual(seg.utileDebut - 1e-9)
      expect(r.fin).toBeLessThanOrEqual(seg.utileFin + 1e-9)
    }
    // Les trois segments portent chacun des rangées.
    expect(new Set(rangees.map((r) => r.segment))).toEqual(new Set([0, 1, 2]))
  })

  it('refuse un arc sans rayon ni largeur, avec le motif de chaque manque', () => {
    const sansRien = validerArc({ segmentsM: [20.55] })
    expect(sansRien.valide).toBe(false)
    expect(sansRien.motifs).toHaveLength(2)
    expect(sansRien.motifs[0]).toMatch(/Rayon extérieur manquant/)
    expect(sansRien.motifs[1]).toMatch(/Largeur de la bande manquante/)

    expect(validerArc({ rayonExtM: 274, segmentsM: [20.55] }).motifs[0]).toMatch(/Largeur/)
    expect(validerArc({ largeurM: 10.9, segmentsM: [20.55] }).motifs[0]).toMatch(/Rayon/)
    expect(validerArc({ rayonExtM: 10, largeurM: 10.9, segmentsM: [1] }).motifs[0]).toMatch(
      /rayon intérieur serait négatif/,
    )
    expect(validerArc({ rayonExtM: 274, largeurM: 10.9, segmentsM: [] }).motifs[0]).toMatch(
      /Aucun segment/,
    )
    expect(validerArc(ARC_REFERENCE)).toEqual({ valide: true, motifs: [] })
  })

  it('le chemin du secteur réel est un arc, jamais un segment droit', () => {
    const arc = decouperArc(ARC_REFERENCE)
    const d = cheminSecteur(arc, arc.segments[0].debut, arc.segments[0].fin, 0, arc.rayonExtM)
    expect(d).toMatch(/^M /)
    expect(d.match(/A /g)).toHaveLength(2) // un arc extérieur + un arc intérieur
    expect(d.endsWith('Z')).toBe(true)
    expect(cheminSecteur({ rayonExtM: 0, rayonIntM: 0, angleTotalRad: 0 }, 0, 1, 0, 0)).toBe('')
  })
})

describe('EnveloppeArc — écran (AOF91)', () => {
  it('rend le développé ET le réel côte à côte, avec 0 rangée à cheval', () => {
    const { container } = render(<EnveloppeArc />)
    expect(container.querySelector('[data-ao-arc-developpe]').dataset.aoArcDeveloppe).toBe(
      '68.05',
    )
    expect(container.querySelector('[data-ao-arc-a-cheval]').dataset.aoArcACheval).toBe('0')
    expect(container.querySelector('[data-ao-arc-rendu="developpe"]')).not.toBeNull()
    expect(container.querySelector('[data-ao-arc-rendu="reel"]')).not.toBeNull()
    // Trois segments et deux murets dans CHACUN des deux rendus.
    expect(container.querySelectorAll('[data-ao-arc-segment]')).toHaveLength(3)
    expect(container.querySelectorAll('[data-ao-arc-segment-reel]')).toHaveLength(3)
    expect(container.querySelectorAll('[data-ao-arc-muret-reel]')).toHaveLength(2)
    expect(screen.getByText(/68,05 m/)).toBeTruthy()
  })

  it('valide l’arc de référence et remonte son découpage', async () => {
    const user = userEvent.setup()
    const onValider = vi.fn()
    render(<EnveloppeArc onValider={onValider} />)
    await user.click(screen.getByRole('button', { name: /Valider l’enveloppe en arc/ }))
    const rendu = onValider.mock.calls[0][0]
    expect(rendu.developpeTotal).toBeCloseTo(68.05, 6)
    expect(rendu.segments).toHaveLength(3)
  })

  it('un arc vidé de son rayon et de sa largeur est refusé à l’écran, avec les motifs', async () => {
    const user = userEvent.setup()
    const onValider = vi.fn()
    const { container } = render(<EnveloppeArc onValider={onValider} />)

    await user.clear(screen.getByLabelText('Rayon extérieur (m)'))
    await user.clear(screen.getByLabelText('Largeur de la bande (m)'))
    await user.click(screen.getByRole('button', { name: /Valider l’enveloppe en arc/ }))

    expect(onValider).not.toHaveBeenCalled()
    const refus = screen.getByRole('alert')
    expect(refus.textContent).toMatch(/Rayon extérieur manquant/)
    expect(refus.textContent).toMatch(/Largeur de la bande manquante/)
    expect(container.querySelector('[data-ao-arc-refus]').dataset.aoArcRefus).toBe('2')
    // Le rendu réel dégrade proprement au lieu d'afficher une courbe fausse.
    expect(screen.getByText(/Rendu réel indisponible/)).toBeTruthy()
  })
})
