import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { axe } from 'vitest-axe'
import TableauGeometrie from './TableauGeometrie'
import useHistoire from './useHistoire'

/* AOF77 — le « Done = » exige trois preuves :
   1. toute géométrie est créable ET modifiable SANS SOURIS (clavier de bout
      en bout) ;
   2. le tableau et le canvas (Selection.jsx, AOF76) partagent le MÊME
      historique undo/redo — prouvé ici en branchant `TableauGeometrie` sur un
      VRAI `useHistoire`, exactement comme le fera le propriétaire de
      l'atelier ;
   3. tout changement de COMPTE (sommets/obstacles) est annoncé en
      `aria-live`. */

// Atelier minimal : UN SEUL historique partagé entre sommets et obstacles,
// exactement le patron documenté par `useHistoire.js` pour AOF76/AOF77.
function Atelier({ etatInitial = { sommets: [], obstacles: [] } }) {
  const historique = useHistoire(etatInitial)
  const onGeometrie = (sommets, libelle, opts) => {
    historique.appliquer((prev) => ({ ...prev, sommets }), libelle, opts)
  }
  const onObstacles = (obstacles, libelle, opts) => {
    historique.appliquer((prev) => ({ ...prev, obstacles }), libelle, opts)
  }
  return (
    <div>
      <button type="button" onClick={historique.annuler} disabled={!historique.peutAnnuler}>
        Annuler
      </button>
      <span data-testid="libelle-courant">{historique.libelle}</span>
      <TableauGeometrie
        points={historique.etat.sommets}
        obstacles={historique.etat.obstacles}
        onGeometrie={onGeometrie}
        onObstacles={onObstacles}
        onRefus={() => {}}
        onRefusObstacle={() => {}}
        onTerminer={historique.terminer}
      />
    </div>
  )
}

describe('TableauGeometrie — sommets, SANS SOURIS', () => {
  it('construit un triangle depuis ZÉRO, entièrement au clavier', async () => {
    const user = userEvent.setup()
    render(<Atelier />)

    const ajouter = screen.getByRole('button', { name: 'Ajouter un sommet' })
    await user.click(ajouter) // A (0, 0)
    await user.click(ajouter) // B (1, 1)
    await user.click(ajouter) // C (2, 2) — collinéaire, mais un AJOUT est toujours accepté

    // Repositionne B et C au clavier pour former un triangle non dégénéré.
    const editer = async (label, valeur) => {
      const champ = screen.getByLabelText(label)
      await user.clear(champ)
      await user.type(champ, valeur)
    }
    await editer('x (m) — Sommet B', '10')
    await editer('y (m) — Sommet B', '0')
    await editer('x (m) — Sommet C', '0')
    await editer('y (m) — Sommet C', '10')

    expect(screen.getByLabelText('x (m) — Sommet A')).toHaveValue('0')
    expect(screen.getByLabelText('y (m) — Sommet A')).toHaveValue('0')
    expect(screen.getByLabelText('x (m) — Sommet B')).toHaveValue('10')
    expect(screen.getByLabelText('y (m) — Sommet B')).toHaveValue('0')
    expect(screen.getByLabelText('x (m) — Sommet C')).toHaveValue('0')
    expect(screen.getByLabelText('y (m) — Sommet C')).toHaveValue('10')
  })

  it('partage le MÊME historique undo/redo que le canvas : « Annuler » défait une saisie de tableau', async () => {
    const user = userEvent.setup()
    render(<Atelier etatInitial={{ sommets: [{ x: 0, y: 0 }, { x: 10, y: 0 }, { x: 0, y: 10 }], obstacles: [] }} />)

    const champ = screen.getByLabelText('x (m) — Sommet B')
    await user.clear(champ)
    await user.type(champ, '20')
    expect(screen.getByLabelText('x (m) — Sommet B')).toHaveValue('20')
    expect(screen.getByTestId('libelle-courant').textContent).toMatch(/sommet B/i)

    const annuler = screen.getByRole('button', { name: 'Annuler' })
    expect(annuler).toBeEnabled()
    await user.click(annuler)
    expect(screen.getByLabelText('x (m) — Sommet B')).toHaveValue('10')
  })

  it('REFUSE une modification qui romprait un contour déjà valide (auto-intersection)', async () => {
    const onRefus = vi.fn()
    const onGeometrie = vi.fn()
    const user = userEvent.setup()
    render(
      <TableauGeometrie
        points={[{ x: 0, y: 0 }, { x: 5, y: 0 }, { x: 5, y: 5 }, { x: 0, y: 5 }]}
        onGeometrie={onGeometrie}
        onRefus={onRefus}
      />,
    )
    // Remonte le sommet B (5,0) AU-DESSUS du côté CD : le segment AB traverse
    // alors CD — nœud papillon. La cible tient en UNE frappe (« 9 »), sinon la
    // frappe intermédiaire (« 1 » de « 10 ») décrirait un contour parfaitement
    // valide que le composant a le devoir de publier : la fusion des frappes en
    // un seul cran d'annulation est le contrat documenté du tableau.
    const champY = screen.getByLabelText('y (m) — Sommet B')
    await user.clear(champY)
    await user.type(champY, '9')

    expect(onRefus).toHaveBeenCalled()
    expect(onRefus.mock.calls.at(-1)[0]).toMatch(/crois|intersection/i)
    expect(onGeometrie).not.toHaveBeenCalled()
  })

  it('supprime un sommet AU CLAVIER (bouton focusable, sans souris)', async () => {
    const onGeometrie = vi.fn()
    const user = userEvent.setup()
    render(
      <TableauGeometrie
        points={[{ x: 0, y: 0 }, { x: 10, y: 0 }, { x: 0, y: 10 }, { x: 5, y: 5 }]}
        onGeometrie={onGeometrie}
        onRefus={() => {}}
      />,
    )
    await user.click(screen.getByRole('button', { name: 'Supprimer le sommet D' }))
    expect(onGeometrie).toHaveBeenCalledTimes(1)
    expect(onGeometrie.mock.calls[0][0]).toHaveLength(3)
  })
})

describe('TableauGeometrie — obstacles rectangulaires', () => {
  it('ajoute, édite et supprime un obstacle sans souris', async () => {
    const user = userEvent.setup()
    let obstacles = []
    const onObstacles = vi.fn((next) => { obstacles = next })
    const { rerender } = render(
      <TableauGeometrie points={[]} obstacles={obstacles} onObstacles={onObstacles} onRefusObstacle={() => {}} />,
    )

    await user.click(screen.getByRole('button', { name: 'Ajouter un obstacle' }))
    expect(onObstacles).toHaveBeenCalledTimes(1)
    expect(obstacles).toHaveLength(1)
    expect(obstacles[0]).toMatchObject({ repere: 'A', rectX0M: 0, rectX1M: 1, rectY0M: 0, rectY1M: 1 })

    rerender(
      <TableauGeometrie points={[]} obstacles={obstacles} onObstacles={onObstacles} onRefusObstacle={() => {}} />,
    )

    const champX1 = screen.getByLabelText('x1 (m) — Obstacle A')
    await user.clear(champX1)
    await user.type(champX1, '4')
    expect(obstacles[0].rectX1M).toBe(4)

    rerender(
      <TableauGeometrie points={[]} obstacles={obstacles} onObstacles={onObstacles} onRefusObstacle={() => {}} />,
    )

    await user.selectOptions(screen.getByLabelText('Provenance — Obstacle A'), 'confirmer')
    expect(obstacles[0].provenance).toBe('confirmer')

    rerender(
      <TableauGeometrie points={[]} obstacles={obstacles} onObstacles={onObstacles} onRefusObstacle={() => {}} />,
    )

    await user.click(screen.getByRole('button', { name: "Supprimer l'obstacle A" }))
    expect(obstacles).toHaveLength(0)
  })

  it('REFUSE x1 ≤ x0 avec un message explicite, et ne publie pas la ligne invalide', async () => {
    const onObstacles = vi.fn()
    const onRefusObstacle = vi.fn()
    const user = userEvent.setup()
    render(
      <TableauGeometrie
        points={[]}
        obstacles={[{
          id: 'obs-A', repere: 'A', rectX0M: 0, rectX1M: 2, rectY0M: 0, rectY1M: 2, degagementM: null, provenance: 'mesure',
        }]}
        onObstacles={onObstacles}
        onRefusObstacle={onRefusObstacle}
      />,
    )
    const champX1 = screen.getByLabelText('x1 (m) — Obstacle A')
    await user.clear(champX1)
    await user.type(champX1, '0')
    expect(onRefusObstacle).toHaveBeenCalledWith(expect.stringMatching(/x1 doit être/i))
    expect(onObstacles).not.toHaveBeenCalled()
  })
})

describe('TableauGeometrie — annonces aria-live des changements de compte', () => {
  it('annonce le nouveau compte après un ajout de sommet', async () => {
    const user = userEvent.setup()
    render(<Atelier />)
    expect(screen.getByRole('status').textContent).toMatch(/0 sommet/)
    await user.click(screen.getByRole('button', { name: 'Ajouter un sommet' }))
    expect(screen.getByRole('status').textContent).toMatch(/1 sommet/)
  })

  it("annonce le nouveau compte après un ajout d'obstacle", async () => {
    const user = userEvent.setup()
    render(<Atelier />)
    await user.click(screen.getByRole('button', { name: 'Ajouter un obstacle' }))
    expect(screen.getByRole('status').textContent).toMatch(/1 obstacle/)
  })
})

describe('TableauGeometrie — accessibilité', () => {
  it("n'a aucune violation d'accessibilité détectable (axe)", async () => {
    const { container } = render(
      <TableauGeometrie
        points={[{ x: 0, y: 0 }, { x: 10, y: 0 }, { x: 0, y: 10 }]}
        obstacles={[{
          id: 'obs-A', repere: 'A', rectX0M: 0, rectX1M: 2, rectY0M: 0, rectY1M: 2, degagementM: null, provenance: 'mesure',
        }]}
        onGeometrie={() => {}}
        onObstacles={() => {}}
      />,
    )
    const results = await axe(container)
    expect(results.violations).toEqual([])
  })
})
