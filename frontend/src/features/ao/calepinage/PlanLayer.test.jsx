import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import PlanLayer from './PlanLayer'

/* AOF92 — le plan rendu est EXACTEMENT celui renvoyé par le serveur :
   aucune position, aucune cote, aucune conversion d'axe côté front. */

// Charge utile SERVEUR — valeurs littérales (le front n'en dérive aucune).
const table = (id, x, y, faitage) => ({ id, x, y, largeur_m: 2.382, hauteur_m: 2.25, faitage })

const PLAN = {
  cadre: { x_min: 0, y_min: 0, largeur_m: 40, hauteur_m: 25 },
  rangees: [
    {
      id: 'R1',
      orientation: 'paysage',
      tables: [
        table('T1', 1.37, 2.19, { x1: 1.37, y1: 3.315, x2: 3.752, y2: 3.315 }),
        table('T2', 3.91, 2.19, { x1: 3.91, y1: 3.315, x2: 6.292, y2: 3.315 }),
      ],
    },
    {
      id: 'R2',
      orientation: 'portrait',
      tables: [table('T3', 1.37, 7.43, { x1: 1.37, y1: 8.555, x2: 3.752, y2: 8.555 })],
    },
  ],
  allees: [{ id: 'A1', x: 0, y: 4.69, largeur_m: 40, hauteur_m: 1.9, cote: { texte: '1,90 m', x: 20, y: 5.5 } }],
  rives: [{ id: 'V1', x: 0, y: 0, largeur_m: 40, hauteur_m: 0.6 }],
  degagements: [{ id: 'D1', x: 12, y: 12, largeur_m: 3, hauteur_m: 3 }],
  obstacles: [{ id: 'O1', repere: 'A', x: 12.5, y: 12.5, largeur_m: 2, hauteur_m: 2, provenance: 'mesure' }],
  zones: [{ id: 'Z1', nom: 'Aile A', contour: [[0, 0], [40, 0], [40, 25], [0, 25]] }],
}

const rects = (container, role) => [...container.querySelectorAll(`rect[data-item="${role}"]`)]

describe('PlanLayer (AOF92)', () => {
  it('pose chaque table aux coordonnées SERVEUR, sans la moindre reprise', () => {
    const { container } = render(<PlanLayer plan={PLAN} />)
    const tables = rects(container, 'table')
    expect(tables).toHaveLength(3)
    expect(tables[0].getAttribute('x')).toBe('1.37')
    expect(tables[0].getAttribute('y')).toBe('2.19')
    expect(tables[0].getAttribute('width')).toBe('2.382')
    expect(tables[0].getAttribute('height')).toBe('2.25')
    // Aucune inversion d'axe : le y de la 3ᵉ table reste celui du serveur.
    expect(tables[2].getAttribute('y')).toBe('7.43')
  })

  it('trace le faîtage aux extrémités renvoyées par le serveur', () => {
    const { container } = render(<PlanLayer plan={PLAN} />)
    const faitages = [...container.querySelectorAll('line[data-item="faitage"]')]
    expect(faitages).toHaveLength(3)
    expect(faitages[0].getAttribute('x1')).toBe('1.37')
    expect(faitages[0].getAttribute('y1')).toBe('3.315')
    expect(faitages[0].getAttribute('x2')).toBe('3.752')
  })

  it("affiche la cote d'allée comme TEXTE serveur (aucun formatage front)", () => {
    render(<PlanLayer plan={PLAN} />)
    expect(screen.getByText('1,90 m')).toBeInTheDocument()
  })

  it('dessine les couches allées / rives / dégagements / obstacles / zones', () => {
    const { container } = render(<PlanLayer plan={PLAN} />)
    expect(rects(container, 'allee')).toHaveLength(1)
    expect(rects(container, 'rive')).toHaveLength(1)
    expect(rects(container, 'degagement')).toHaveLength(1)
    expect(rects(container, 'obstacle')).toHaveLength(1)
    expect(container.querySelectorAll('polygon[data-item="zone"]')).toHaveLength(1)
    expect(container.querySelector('[data-ao-repere="A"]')).toBeInTheDocument()
  })

  it('expose UN seul canvas repéré `data-ao-canvas`', () => {
    const { container } = render(<PlanLayer plan={PLAN} />)
    expect(container.querySelectorAll('[data-ao-canvas]')).toHaveLength(1)
  })

  it('génère la légende depuis les couches PRÉSENTES (jamais une liste figée)', () => {
    const { container } = render(<PlanLayer plan={PLAN} />)
    const cles = [...container.querySelectorAll('[data-legende]')].map((li) => li.getAttribute('data-legende'))
    expect(cles).toEqual(['zones', 'allees', 'rives', 'degagements', 'obstacles', 'tables'])
  })

  it('retire de la légende les couches absentes de la charge utile', () => {
    const { container } = render(<PlanLayer plan={{ ...PLAN, obstacles: [], zones: [] }} />)
    const cles = [...container.querySelectorAll('[data-legende]')].map((li) => li.getAttribute('data-legende'))
    expect(cles).toEqual(['allees', 'rives', 'degagements', 'tables'])
  })

  it('reprend le libellé de légende du serveur quand il en fournit un', () => {
    render(<PlanLayer plan={{ ...PLAN, legende: [{ cle: 'tables', libelle: 'Tables dos-à-dos 2 modules' }] }} />)
    expect(screen.getByText('Tables dos-à-dos 2 modules')).toBeInTheDocument()
  })

  it('zoome sur 314 tables sans toucher UNE SEULE coordonnée', () => {
    const grosPlan = {
      ...PLAN,
      rangees: [{
        id: 'R',
        orientation: 'paysage',
        tables: Array.from({ length: 314 }, (unused, i) => table(`T${i}`, i, 3, null)),
      }],
    }
    const { container, rerender } = render(<PlanLayer plan={grosPlan} zoom={1} />)
    expect(rects(container, 'table')).toHaveLength(314)
    const avant = rects(container, 'table').map((r) => r.getAttribute('x'))
    const viewBoxAvant = container.querySelector('[data-ao-canvas]').getAttribute('viewBox')

    rerender(<PlanLayer plan={grosPlan} zoom={4} />)
    const apres = rects(container, 'table').map((r) => r.getAttribute('x'))
    const viewBoxApres = container.querySelector('[data-ao-canvas]').getAttribute('viewBox')

    expect(apres).toEqual(avant)          // la géométrie ne bouge pas…
    expect(viewBoxApres).not.toBe(viewBoxAvant) // …seule la fenêtre change.
  })

  it('la fenêtre se rétrécit autour du centre du cadre quand on zoome', () => {
    const cadre = { cadre: { x_min: 0, y_min: 0, largeur_m: 40, hauteur_m: 20 }, rangees: PLAN.rangees }
    const { container, rerender } = render(<PlanLayer plan={cadre} zoom={1} />)
    expect(container.querySelector('[data-ao-canvas]').getAttribute('viewBox')).toBe('0 0 40 20')
    rerender(<PlanLayer plan={cadre} zoom={2} />)
    expect(container.querySelector('[data-ao-canvas]').getAttribute('viewBox')).toBe('10 5 20 10')
  })

  it('ne rend rien sans cadre serveur (pas de plan inventé côté front)', () => {
    const { container } = render(<PlanLayer plan={{ rangees: [] }} />)
    expect(container.querySelector('[data-ao-canvas]')).toBeNull()
  })
})

/* ============================================================================
   PV31 — bandes d'accroche du mode « rangées imposées par l'utilisateur ».
   ----------------------------------------------------------------------------
   `getBoundingClientRect` est simulé sur le SVG (même patron que
   `GanttChart.test.jsx` pour son drag-to-reposition) : jsdom ne mesure jamais
   un vrai layout, et ni `getScreenCTM` ni `createSVGPoint` n'y existent.
   ========================================================================== */
describe('PlanLayer (PV31) — bandes d’accroche des rangées imposées', () => {
  const RANGEES = [[2, 'AO-TABLE-PORTRAIT'], [10, 'AO-TABLE-PORTRAIT']]

  it('sans `rangeesImposees`, aucune bande n’apparaît (compatibilité arrière)', () => {
    const { container } = render(<PlanLayer plan={PLAN} />)
    expect(container.querySelectorAll('[data-item="rangee-bande"]')).toHaveLength(0)
  })

  it('une bande par rangée, à son y0 RÉEL, avec son index en attribut', () => {
    const { container } = render(<PlanLayer plan={PLAN} rangeesImposees={RANGEES} />)
    const bandes = [...container.querySelectorAll('[data-item="rangee-bande"]')]
    expect(bandes).toHaveLength(2)
    expect(bandes[0].getAttribute('y')).toBe('2')
    expect(bandes[1].getAttribute('y')).toBe('10')
    expect(bandes[0].getAttribute('data-rangee-index')).toBe('0')
    expect(bandes[1].getAttribute('data-rangee-index')).toBe('1')
  })

  it('la rangée sélectionnée porte `data-rangee-selectionnee`, jamais une autre', () => {
    const { container } = render(
      <PlanLayer plan={PLAN} rangeesImposees={RANGEES} rangeeSelectionnee={1} />,
    )
    const bandes = [...container.querySelectorAll('[data-item="rangee-bande"]')]
    expect(bandes[0].getAttribute('data-rangee-selectionnee')).toBeNull()
    expect(bandes[1].getAttribute('data-rangee-selectionnee')).toBe('true')
  })

  it('pointerdown sur une bande appelle `onRangeePointerDown`, JAMAIS `onFondPointerDown`', () => {
    const onRangeePointerDown = vi.fn()
    const onFondPointerDown = vi.fn()
    const { container } = render(
      <PlanLayer
        plan={PLAN}
        rangeesImposees={RANGEES}
        onRangeePointerDown={onRangeePointerDown}
        onFondPointerDown={onFondPointerDown}
      />,
    )
    fireEvent.pointerDown(container.querySelector('[data-rangee-index="1"]'))
    expect(onRangeePointerDown).toHaveBeenCalledWith(1, expect.anything())
    expect(onFondPointerDown).not.toHaveBeenCalled()
  })

  it('pointerdown sur le FOND calcule l’ordonnée SVG et appelle `onFondPointerDown`', () => {
    const onFondPointerDown = vi.fn()
    const { container } = render(<PlanLayer plan={PLAN} onFondPointerDown={onFondPointerDown} />)
    const svg = container.querySelector('[data-ao-canvas]')
    vi.spyOn(svg, 'getBoundingClientRect').mockReturnValue({ top: 100, height: 250 })

    // viewBox = « 0 0 40 25 » (cadre de PLAN) ; clientY à mi-hauteur du SVG
    // simulé (100 + 125) doit tomber à mi-hauteur du cadre (12,5 m).
    fireEvent.pointerDown(svg, { clientY: 225 })

    expect(onFondPointerDown).toHaveBeenCalledTimes(1)
    expect(onFondPointerDown.mock.calls[0][0]).toBeCloseTo(12.5, 5)
  })

  it('un pointerdown sur une bande n’atteint jamais le fond (stopPropagation)', () => {
    const onFondPointerDown = vi.fn()
    const { container } = render(
      <PlanLayer plan={PLAN} rangeesImposees={RANGEES} onFondPointerDown={onFondPointerDown} />,
    )
    fireEvent.pointerDown(container.querySelector('[data-rangee-index="0"]'))
    expect(onFondPointerDown).not.toHaveBeenCalled()
  })

  it('pointermove/pointerup relaient l’ordonnée SVG au canvas', () => {
    const onPointerMoveSvg = vi.fn()
    const onPointerUpSvg = vi.fn()
    const { container } = render(
      <PlanLayer plan={PLAN} onPointerMoveSvg={onPointerMoveSvg} onPointerUpSvg={onPointerUpSvg} />,
    )
    const svg = container.querySelector('[data-ao-canvas]')
    vi.spyOn(svg, 'getBoundingClientRect').mockReturnValue({ top: 100, height: 250 })

    fireEvent.pointerMove(svg, { clientY: 100 })
    expect(onPointerMoveSvg).toHaveBeenCalledWith(0, expect.anything())

    fireEvent.pointerUp(svg)
    expect(onPointerUpSvg).toHaveBeenCalledTimes(1)
  })

  it('`yPropose` dessine un TRAIT pointillé, jamais un rectangle (pas de table inventée)', () => {
    const { container } = render(<PlanLayer plan={PLAN} yPropose={5} />)
    const ligne = container.querySelector('[data-item="rangee-proposee"]')
    expect(ligne).not.toBeNull()
    expect(ligne.tagName.toLowerCase()).toBe('line')
    expect(ligne.getAttribute('y1')).toBe('5')
    expect(ligne.getAttribute('y2')).toBe('5')
    expect(container.querySelector('rect[data-item="rangee-proposee"]')).toBeNull()
  })

  it('sans glissé en cours, aucune ligne proposée', () => {
    const { container } = render(<PlanLayer plan={PLAN} />)
    expect(container.querySelector('[data-item="rangee-proposee"]')).toBeNull()
  })
})
