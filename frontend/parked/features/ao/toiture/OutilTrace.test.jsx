import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import OutilTrace from './OutilTrace'

/* AOF84 — le « Done = » exige trois preuves :
   1. le rectangle 25,62 × 51,10 se saisit ENTIÈREMENT au clavier ;
   2. l'auto-intersection est refusée ;
   3. l'annulation se fait étape par étape. */

async function saisirSegment(user, longueur, touche) {
  const champ = screen.getByLabelText('Longueur (m)')
  await user.clear(champ)
  await user.type(champ, longueur)
  await user.keyboard(touche)
}

describe('OutilTrace (AOF84)', () => {
  it('saisit un rectangle de 25,62 × 51,10 ENTIÈREMENT au clavier', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(<OutilTrace onChange={onChange} />)

    // Départ implicite en (0, 0) : trois segments + fermeture suffisent.
    await saisirSegment(user, '25.62', '{ArrowRight}')
    await saisirSegment(user, '51.10', '{ArrowUp}')
    await saisirSegment(user, '25.62', '{ArrowLeft}')
    await user.click(screen.getByRole('button', { name: 'Fermer le contour' }))

    const dernier = onChange.mock.calls.at(-1)[0]
    expect(dernier.ferme).toBe(true)
    expect(dernier.sommets_m).toEqual([
      { x: 0, y: 0 },
      { x: 25.62, y: 0 },
      { x: 25.62, y: 51.1 },
      { x: 0, y: 51.1 },
    ])
    // L'aire affichée est bien celle du rectangle relevé.
    expect(document.querySelector('[data-ao-trace-etat]').textContent).toMatch(/1309\.18 m²/)
  })

  it('accepte un angle en degrés validé par Entrée (pan oblique)', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(<OutilTrace onChange={onChange} />)
    await user.type(screen.getByLabelText('Angle (°)'), '90')
    await user.type(screen.getByLabelText('Longueur (m)'), '10')
    await user.keyboard('{Enter}')
    const dernier = onChange.mock.calls.at(-1)[0]
    expect(dernier.sommets_m[1].x).toBeCloseTo(0, 6)
    expect(dernier.sommets_m[1].y).toBeCloseTo(10, 6)
  })

  it('trace un « L » d’un seul tenant (décrochement, jamais deux rectangles)', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(<OutilTrace onChange={onChange} />)
    await saisirSegment(user, '30', '{ArrowRight}')
    await saisirSegment(user, '12', '{ArrowUp}')
    await saisirSegment(user, '18', '{ArrowLeft}')
    await saisirSegment(user, '28', '{ArrowUp}')
    await saisirSegment(user, '12', '{ArrowLeft}')
    await user.click(screen.getByRole('button', { name: 'Fermer le contour' }))

    const dernier = onChange.mock.calls.at(-1)[0]
    expect(dernier.ferme).toBe(true)
    expect(dernier.sommets_m).toHaveLength(6)
    // 30×12 + 12×28 = 696 m², d'un seul tenant.
    expect(document.querySelector('[data-ao-trace-etat]').textContent).toMatch(/696\.00 m²/)
  })

  it('REFUSE un segment qui croiserait le tracé (auto-intersection)', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(<OutilTrace onChange={onChange} />)
    await saisirSegment(user, '10', '{ArrowRight}')
    await saisirSegment(user, '10', '{ArrowUp}')
    await saisirSegment(user, '5', '{ArrowLeft}')
    const avant = onChange.mock.calls.length
    // Ce segment redescend en x = 5 et retraverserait le premier segment (y = 0).
    await saisirSegment(user, '20', '{ArrowDown}')

    expect(screen.getByRole('alert').textContent).toMatch(/auto-intersection/i)
    expect(onChange.mock.calls.length).toBe(avant) // rien n'a été ajouté
  })

  it('refuse de fermer un contour de moins de trois sommets', async () => {
    const user = userEvent.setup()
    render(<OutilTrace onChange={() => {}} />)
    await saisirSegment(user, '10', '{ArrowRight}')
    await user.click(screen.getByRole('button', { name: 'Fermer le contour' }))
    expect(screen.getByRole('alert').textContent).toMatch(/au moins trois sommets/i)
  })

  it('annule ÉTAPE PAR ÉTAPE : d’abord la fermeture, puis chaque sommet', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(<OutilTrace onChange={onChange} />)
    await saisirSegment(user, '25.62', '{ArrowRight}')
    await saisirSegment(user, '51.10', '{ArrowUp}')
    await saisirSegment(user, '25.62', '{ArrowLeft}')
    await user.click(screen.getByRole('button', { name: 'Fermer le contour' }))
    expect(onChange.mock.calls.at(-1)[0].ferme).toBe(true)

    const annuler = screen.getByRole('button', { name: 'Annuler la dernière étape' })
    await user.click(annuler)
    expect(onChange.mock.calls.at(-1)[0].ferme).toBe(false)
    expect(onChange.mock.calls.at(-1)[0].sommets_m).toHaveLength(4)

    await user.click(annuler)
    expect(onChange.mock.calls.at(-1)[0].sommets_m).toHaveLength(3)
    await user.click(annuler)
    expect(onChange.mock.calls.at(-1)[0].sommets_m).toHaveLength(2)
  })

  it('ferme automatiquement quand le segment retombe sur le point de départ', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(<OutilTrace onChange={onChange} />)
    await saisirSegment(user, '10', '{ArrowRight}')
    await saisirSegment(user, '10', '{ArrowUp}')
    await saisirSegment(user, '10', '{ArrowLeft}')
    await saisirSegment(user, '10', '{ArrowDown}')
    const dernier = onChange.mock.calls.at(-1)[0]
    expect(dernier.ferme).toBe(true)
    expect(dernier.sommets_m).toHaveLength(4)
  })

  it('une longueur absente est refusée avec un message FR', async () => {
    const user = userEvent.setup()
    render(<OutilTrace onChange={() => {}} />)
    await user.click(screen.getByLabelText('Longueur (m)'))
    await user.keyboard('{ArrowRight}')
    expect(screen.getByRole('alert').textContent).toMatch(/longueur en mètres/i)
  })

  it('insère et supprime un sommet', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(<OutilTrace onChange={onChange} />)
    await saisirSegment(user, '10', '{ArrowRight}')
    await saisirSegment(user, '10', '{ArrowUp}')
    await user.click(screen.getByRole('button', { name: 'Insérer après S1' }))
    expect(onChange.mock.calls.at(-1)[0].sommets_m).toHaveLength(4)
    await user.click(screen.getByRole('button', { name: 'Supprimer S2' }))
    expect(onChange.mock.calls.at(-1)[0].sommets_m).toHaveLength(3)
  })
})
