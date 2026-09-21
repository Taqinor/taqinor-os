import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ChainesCotes from './ChainesCotes'
import Cote from './Cote'

/* AOF85 — chaînes créables sur les DEUX axes, cotes lisibles à tous les zooms,
   couleur pilotée par la PROVENANCE (tokens AOF9, jamais un hex en dur). */

describe('Cote (primitive de cotation, AOF85)', () => {
  it('rend le vocabulaire d’une cote de plan : attaches, ligne, double flèche, texte', () => {
    render(
      <svg>
        <Cote x1={0} y1={0} x2={25.62} y2={0} valeur={25.62} axe="x" decalage={1} />
      </svg>,
    )
    const groupe = document.querySelector('[data-ao-cote]')
    expect(groupe.querySelectorAll('line')).toHaveLength(3) // 2 attaches + 1 ligne de cote
    expect(groupe.querySelectorAll('polyline')).toHaveLength(2) // double flèche
    expect(groupe.querySelector('[data-ao-cote-texte]').textContent).toBe('25,62 m')
  })

  it('reste lisible à tous les zooms : le corps du texte est en pixels ÉCRAN', () => {
    const { rerender } = render(
      <svg>
        <Cote x1={0} y1={0} x2={10} y2={0} valeur={10} pixelsParMetre={1} />
      </svg>,
    )
    const taille1 = Number(document.querySelector('[data-ao-cote-texte]').getAttribute('font-size'))
    rerender(
      <svg>
        <Cote x1={0} y1={0} x2={10} y2={0} valeur={10} pixelsParMetre={4} />
      </svg>,
    )
    const taille4 = Number(document.querySelector('[data-ao-cote-texte]').getAttribute('font-size'))
    // Le groupe est mis à l'échelle ×4 : le corps doit être divisé par 4 pour
    // rendre la MÊME taille à l'écran.
    expect(taille4).toBeCloseTo(taille1 / 4, 6)
  })

  it('la couleur vient du token de provenance, jamais d’un hexadécimal', () => {
    render(
      <svg>
        <Cote x1={0} y1={0} x2={10} y2={0} valeur={10} provenance="confirmer" />
      </svg>,
    )
    const groupe = document.querySelector('[data-ao-cote]')
    expect(groupe.getAttribute('stroke')).toBe('var(--ao-provenance-confirmer, currentColor)')
    expect(groupe.getAttribute('stroke')).not.toMatch(/#[0-9a-f]{3,8}/i)
    expect(groupe.getAttribute('data-ao-cote-provenance')).toBe('confirmer')
  })

  it('une provenance inconnue retombe sur « mesuré » plutôt que sur du vide', () => {
    render(
      <svg>
        <Cote x1={0} y1={0} x2={10} y2={0} valeur={10} provenance="n’importe quoi" />
      </svg>,
    )
    expect(document.querySelector('[data-ao-cote]').getAttribute('stroke')).toBe(
      'var(--ao-provenance-mesure, currentColor)',
    )
  })

  it('le texte d’une cote verticale est tourné d’un quart de tour', () => {
    render(
      <svg>
        <Cote x1={0} y1={0} x2={0} y2={51.1} valeur={51.1} axe="y" />
      </svg>,
    )
    expect(document.querySelector('[data-ao-cote-texte]').getAttribute('transform')).toMatch(
      /rotate\(-90/,
    )
  })
})

describe('ChainesCotes (AOF85)', () => {
  it('crée des chaînes sur les DEUX axes', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(<ChainesCotes onChange={onChange} />)
    await user.click(screen.getByRole('button', { name: 'Nouvelle chaîne horizontale' }))
    await user.click(screen.getByRole('button', { name: 'Nouvelle chaîne verticale' }))

    const axes = onChange.mock.calls.at(-1)[0].map((c) => c.axe)
    expect(axes).toEqual(['x', 'y'])
    expect(document.querySelectorAll('[data-ao-chaine-axe="x"]').length).toBeGreaterThan(0)
    expect(document.querySelectorAll('[data-ao-chaine-axe="y"]').length).toBeGreaterThan(0)
  })

  it('cumule les segments et affiche la somme face à la cote mesurée', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(
      <ChainesCotes
        onChange={onChange}
        chainesInitiales={[
          {
            id: 'c1',
            axe: 'x',
            nom: 'Façade sud',
            origine: { x: 0, y: 0 },
            tolerance: 0.05,
            coteMesuree: 25.62,
            segments: [
              { id: 's1', libelle: 'A', valeur: 4.1, provenance: 'mesure' },
              { id: 's2', libelle: 'B', valeur: 8.82, provenance: 'confirmer' },
              { id: 's3', libelle: 'C', valeur: 12.7, provenance: 'mesure' },
            ],
          },
        ]}
      />,
    )
    expect(document.querySelector('[data-ao-chaine-somme="c1"]').textContent).toMatch(/25\.62 m/)

    // Édition inline d'un segment : la somme suit immédiatement.
    const champ = screen.getByLabelText('Longueur du segment B')
    await user.clear(champ)
    await user.type(champ, '9')
    expect(document.querySelector('[data-ao-chaine-somme="c1"]').textContent).toMatch(/25\.80 m/)
  })

  it('changer la provenance d’un segment change la couleur de SA cote', async () => {
    const user = userEvent.setup()
    render(
      <ChainesCotes
        chainesInitiales={[
          {
            id: 'c1',
            axe: 'x',
            nom: 'Façade sud',
            origine: { x: 0, y: 0 },
            tolerance: 0.05,
            coteMesuree: 4.1,
            segments: [{ id: 's1', libelle: 'A', valeur: 4.1, provenance: 'mesure' }],
          },
        ]}
      />,
    )
    expect(document.querySelector('[data-ao-cote-provenance="mesure"]')).toBeTruthy()
    await user.selectOptions(screen.getByLabelText('Provenance du segment A'), 'devine')
    expect(document.querySelector('[data-ao-cote-provenance="devine"]')).toBeTruthy()
    expect(
      document.querySelector('[data-ao-cote-provenance="devine"]').getAttribute('stroke'),
    ).toBe('var(--ao-provenance-devine, currentColor)')
  })

  it('ajoute et supprime un segment d’une chaîne', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(<ChainesCotes onChange={onChange} />)
    await user.click(screen.getByRole('button', { name: 'Nouvelle chaîne horizontale' }))
    const nom = onChange.mock.calls.at(-1)[0][0].nom
    await user.click(screen.getByRole('button', { name: `Ajouter un segment à ${nom}` }))
    expect(onChange.mock.calls.at(-1)[0][0].segments).toHaveLength(1)
    await user.click(screen.getByRole('button', { name: 'Supprimer S1' }))
    expect(onChange.mock.calls.at(-1)[0][0].segments).toHaveLength(0)
  })

  it('chaque chaîne porte SA tolérance', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(<ChainesCotes onChange={onChange} />)
    await user.click(screen.getByRole('button', { name: 'Nouvelle chaîne verticale' }))
    await user.selectOptions(screen.getByLabelText('Tolérance (m)'), '0.25')
    expect(onChange.mock.calls.at(-1)[0][0].tolerance).toBe(0.25)
  })
})
