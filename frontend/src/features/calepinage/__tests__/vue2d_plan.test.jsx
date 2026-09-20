import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'

/* ============================================================================
   CAL104 — VUE 2D PLAN + PLEIN ÉCRAN.
   ----------------------------------------------------------------------------
   Ce que ce fichier prouve :
     * le plan affiche le MÊME compte de modules que la 3D — et, s'il diverge, il
       le DIT au lieu de choisir un chiffre ;
     * les COTES affichées sont les longueurs réelles reçues, pas des mesures
       refaites à l'écran ;
     * le plein écran est RÉVERSIBLE et ne démonte rien (donc ne perd ni
       sélection ni historique) ;
     * sans contour fermé, l'écran le dit au lieu de dessiner un plan inventé.
   ========================================================================== */

import Vue2DPlan from '../Vue2DPlan'
import { formatCote, milieu } from '../plan2d'

/** Plan factice, tel que `projectPlanView` le rend (déjà projeté). */
const PLAN = {
  outline: [
    [0, 0],
    [100, 0],
    [100, 60],
    [0, 60],
  ],
  panels: [
    [
      [10, 10],
      [30, 10],
      [30, 40],
      [10, 40],
    ],
    [
      [40, 10],
      [60, 10],
      [60, 40],
      [40, 40],
    ],
  ],
  pxPerM: 10,
  spanEastWestM: 10,
  spanNorthSouthM: 6,
  cotes: [
    { lengthM: 10, from: [0, 0], to: [100, 0] },
    { lengthM: 6, from: [100, 0], to: [100, 60] },
    { lengthM: 10, from: [100, 60], to: [0, 60] },
    { lengthM: 6, from: [0, 60], to: [0, 0] },
  ],
  panelCount: 2,
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('CAL104 — cotes et compte', () => {
  it('une cote est formatée en mètres, jamais réinventée', () => {
    expect(formatCote(10)).toBe('10,00 m')
    expect(formatCote(6.125)).toBe('6,13 m')
    expect(formatCote(undefined)).toBe('—')
  })

  it('le milieu d’un segment porte l’étiquette', () => {
    expect(milieu([0, 0], [100, 60])).toEqual([50, 30])
  })

  it('le plan affiche le compte de modules et les quatre cotes reçus', () => {
    render(<Vue2DPlan plan={PLAN} compte3d={2} />)
    expect(screen.getByTestId('v2d-compte').textContent).toBe('2')
    expect(screen.getAllByTestId('v2d-module')).toHaveLength(2)
    expect(screen.getAllByTestId('v2d-cote').map((n) => n.textContent)).toEqual([
      '10,00 m',
      '6,00 m',
      '10,00 m',
      '6,00 m',
    ])
    expect(screen.queryByTestId('v2d-divergence')).toBeNull()
  })

  it('si la 3D affiche un AUTRE compte, l’écran le dit au lieu de trancher', () => {
    render(<Vue2DPlan plan={PLAN} compte3d={7} />)
    const note = screen.getByTestId('v2d-divergence')
    expect(note.textContent).toContain('7')
    // Le plan continue d'afficher SON compte, il n'invente pas celui de la 3D.
    expect(screen.getByTestId('v2d-compte').textContent).toBe('2')
  })

  it('sans contour fermé, rien n’est dessiné et l’écran le dit', () => {
    render(<Vue2DPlan plan={null} compte3d={0} />)
    expect(screen.getByTestId('v2d-vide')).toBeTruthy()
    expect(screen.queryByTestId('v2d-svg')).toBeNull()
  })
})

describe('CAL104 — plein écran réversible', () => {
  it('bascule et revient, sans jamais démonter la vue (ni sélection ni historique perdus)', async () => {
    const requestFullscreen = vi.fn().mockResolvedValue(undefined)
    const exitFullscreen = vi.fn().mockResolvedValue(undefined)
    render(<Vue2DPlan plan={PLAN} compte3d={2} />)
    const boite = screen.getByTestId('v2d-boite')
    boite.requestFullscreen = requestFullscreen
    document.exitFullscreen = exitFullscreen
    const svgAvant = screen.getByTestId('v2d-svg')

    await act(async () => {
      fireEvent.click(screen.getByTestId('v2d-plein-ecran'))
    })
    expect(requestFullscreen).toHaveBeenCalledTimes(1)
    expect(screen.getByTestId('v2d-boite').dataset.pleinEcran).toBe('1')

    await act(async () => {
      fireEvent.click(screen.getByTestId('v2d-plein-ecran'))
    })
    expect(screen.getByTestId('v2d-boite').dataset.pleinEcran).toBe('0')
    // MÊME nœud SVG du début à la fin : rien n'a été remonté.
    expect(screen.getByTestId('v2d-svg')).toBe(svgAvant)
  })

  it('navigateur sans API Fullscreen ⇒ repli plein cadre, toujours réversible', async () => {
    render(<Vue2DPlan plan={PLAN} compte3d={2} />)
    const boite = screen.getByTestId('v2d-boite')
    boite.requestFullscreen = undefined
    await act(async () => {
      fireEvent.click(screen.getByTestId('v2d-plein-ecran'))
    })
    expect(screen.getByTestId('v2d-boite').dataset.pleinEcran).toBe('1')
    await act(async () => {
      fireEvent.click(screen.getByTestId('v2d-plein-ecran'))
    })
    expect(screen.getByTestId('v2d-boite').dataset.pleinEcran).toBe('0')
  })
})
