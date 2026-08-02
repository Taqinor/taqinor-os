import { describe, it, expect, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import OutilsZones from './OutilsZones'

/* AOF89 — le moteur porte QUATRE natures de contour ; l'éditeur d'obstacles n'en
   sait dessiner qu'une (le rectangle). Sans cet outil polygone, trois natures sur
   quatre seraient inatteignables depuis l'écran, donc du code mort côté moteur.
   Ce qui est prouvé ici :
     1. les trois natures se saisissent ET se relisent,
     2. une zone PRÉFÉRÉE ne retire aucune surface et ne bouge pas le compte du
        moteur (comparaison écran ↔ résultat serveur),
     3. la légende est générée depuis les natures RÉELLEMENT présentes,
     4. un polygone dégénéré ou auto-intersecté est refusé avec son motif. */

const CARRE_10 = [
  { x: 0, y: 0 },
  { x: 10, y: 0 },
  { x: 10, y: 10 },
  { x: 0, y: 10 },
]

const CARRE_4 = [
  { x: 20, y: 20 },
  { x: 24, y: 20 },
  { x: 24, y: 24 },
  { x: 20, y: 24 },
]

// Un « papillon » : les deux diagonales se croisent, aire inexploitable.
const PAPILLON = [
  { x: 0, y: 0 },
  { x: 10, y: 10 },
  { x: 10, y: 0 },
  { x: 0, y: 10 },
]

async function tracer(user, libelleNature, points) {
  await user.click(screen.getByRole('button', { name: libelleNature }))
  for (const p of points) {
    await user.clear(screen.getByLabelText('Point x (m)'))
    await user.type(screen.getByLabelText('Point x (m)'), String(p.x))
    await user.clear(screen.getByLabelText('Point y (m)'))
    await user.type(screen.getByLabelText('Point y (m)'), String(p.y))
    await user.click(screen.getByRole('button', { name: 'Ajouter le point' }))
  }
  await user.click(screen.getByRole('button', { name: /Terminer la zone/ }))
}

function surfaceRetiree(container) {
  return Number(
    container.querySelector('[data-ao-zones-surface-retiree]').dataset.aoZonesSurfaceRetiree,
  )
}

describe('OutilsZones (AOF89)', () => {
  it('les trois natures se saisissent et se relisent', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    const { container } = render(<OutilsZones onChange={onChange} />)

    await tracer(user, 'Zone interdite', CARRE_10)
    await tracer(user, 'Zone réservée', CARRE_4)
    await tracer(user, 'Zone préférée', PAPILLON.slice(0, 3))

    const dernieres = onChange.mock.calls.at(-1)[0]
    expect(dernieres.map((z) => z.nature)).toEqual(['interdite', 'reservee', 'preferee'])
    expect(container.querySelectorAll('[data-ao-zone-nature]')).toHaveLength(3)
    expect(container.querySelector('[data-ao-zone-nature="reservee"]')).not.toBeNull()
    expect(container.querySelector('[data-ao-zone-nature="preferee"]')).not.toBeNull()

    // Relecture : les mêmes zones réinjectées rendent à l'identique.
    const relu = render(<OutilsZones zonesInitiales={dernieres} />)
    expect(relu.container.querySelectorAll('[data-ao-zone-nature]')).toHaveLength(3)
    expect(relu.container.querySelector('[data-ao-zones]').dataset.aoZones).toBe('3')
  })

  it("une zone préférée ne retire aucune surface et ne bouge pas le compte du moteur", async () => {
    const user = userEvent.setup()
    const { container } = render(<OutilsZones compteServeur={314} />)

    await tracer(user, 'Zone interdite', CARRE_10)
    const avant = surfaceRetiree(container)
    expect(avant).toBeCloseTo(100, 2)
    expect(container.querySelector('[data-ao-zones-compte]').dataset.aoZonesCompte).toBe('314')

    // La zone préférée fait 16 m² : si elle retirait de la surface, on lirait 116.
    await tracer(user, 'Zone préférée', CARRE_4)
    expect(surfaceRetiree(container)).toBeCloseTo(avant, 2)
    expect(container.querySelector('[data-ao-zones-compte]').dataset.aoZonesCompte).toBe('314')

    // La zone réservée, elle, retire bien.
    await tracer(user, 'Zone réservée', [
      { x: 30, y: 30 },
      { x: 32, y: 30 },
      { x: 32, y: 32 },
      { x: 30, y: 32 },
    ])
    expect(surfaceRetiree(container)).toBeCloseTo(avant + 4, 2)

    // La règle est écrite en clair et en permanence, indépendamment de la légende.
    expect(container.querySelector('[data-ao-zones-regle]').textContent).toMatch(
      /ne change JAMAIS le compte/i,
    )
  })

  it('la légende est générée depuis les natures réellement présentes', async () => {
    const user = userEvent.setup()
    const { container } = render(<OutilsZones />)
    expect(container.querySelector('[data-ao-zones-legende]')).toBeNull()

    await tracer(user, 'Zone interdite', CARRE_10)
    let legende = container.querySelector('[data-ao-zones-legende]')
    expect(legende.dataset.aoZonesLegende).toBe('1')
    expect(within(legende).queryByText(/Zone réservée/)).toBeNull()

    await tracer(user, 'Zone préférée', CARRE_4)
    legende = container.querySelector('[data-ao-zones-legende]')
    expect(legende.dataset.aoZonesLegende).toBe('2')
    expect(legende.querySelector('[data-ao-zone-legende="preferee"]')).not.toBeNull()
    expect(legende.querySelector('[data-ao-zone-legende="reservee"]')).toBeNull()
  })

  it('changer la nature depuis la liste met la légende et la surface à jour', async () => {
    const user = userEvent.setup()
    const { container } = render(
      <OutilsZones
        zonesInitiales={[{ id: 'z1', nature: 'interdite', nom: 'Zone interdite 1', sommets: CARRE_10 }]}
      />,
    )
    expect(surfaceRetiree(container)).toBeCloseTo(100, 2)

    await user.selectOptions(
      screen.getByLabelText('Nature de Zone interdite 1'),
      'preferee',
    )
    expect(surfaceRetiree(container)).toBeCloseTo(0, 2)
    expect(
      container.querySelector('[data-ao-zones-legende]').dataset.aoZonesLegende,
    ).toBe('1')
  })

  it('un polygone dégénéré ou auto-intersecté est refusé avec son motif', async () => {
    const user = userEvent.setup()
    const { container } = render(<OutilsZones />)

    await tracer(user, 'Zone interdite', [
      { x: 0, y: 0 },
      { x: 5, y: 0 },
    ])
    expect(screen.getByRole('alert').textContent).toMatch(/au moins trois points/i)
    expect(container.querySelectorAll('[data-ao-zone-nature]')).toHaveLength(0)

    const { container: c2 } = render(<OutilsZones />)
    await user.click(within(c2).getByRole('button', { name: 'Zone interdite' }))
    for (const p of PAPILLON) {
      await user.clear(within(c2).getByLabelText('Point x (m)'))
      await user.type(within(c2).getByLabelText('Point x (m)'), String(p.x))
      await user.clear(within(c2).getByLabelText('Point y (m)'))
      await user.type(within(c2).getByLabelText('Point y (m)'), String(p.y))
      await user.click(within(c2).getByRole('button', { name: 'Ajouter le point' }))
    }
    await user.click(within(c2).getByRole('button', { name: /Terminer la zone/ }))
    expect(within(c2).getByRole('alert').textContent).toMatch(/se recoupe/i)
    expect(c2.querySelectorAll('[data-ao-zone-nature]')).toHaveLength(0)
  })
})
