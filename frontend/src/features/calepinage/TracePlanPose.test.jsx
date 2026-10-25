import { describe, it, expect, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import TracePlanPose from './TracePlanPose'
import { planVue2D } from './ModeTerrain.helpers'
import { formatCote } from './plan2d'

/* ENF19 — le tracé partagé du terrain et de l'ombrière : les `data-testid`
   restent ceux de CHAQUE écran (passés en `ids`), la cote du pas n'existe que
   si l'écran en fournit les identifiants, et la ligne d'emprise reprend le
   compte du SERVICE (`champ`), jamais le nombre de formes dessinées. */

afterEach(() => { cleanup() })

const VUE = planVue2D({
  contourM: [[0, 0], [30, 0], [30, 12], [0, 12]],
  tables: [
    { cx: 3, cy: 2, largeurM: 4, profondeurM: 2 },
    { cx: 9, cy: 7, largeurM: 4, profondeurM: 2 },
    { cx: 15, cy: 12, largeurM: 4, profondeurM: 2 },
  ],
  rangees: [{ y0: 2 }, { y0: 7 }, { y0: 12 }],
  pasM: 5,
  compteModules: 18,
})
const CHAMP = { empriseTablesM2: 24, modules: 18 }
const IDS = {
  svg: 'x-svg', contour: 'x-contour', rangee: 'x-rangee', table: 'x-table', cote: 'x-cote', emprise: 'x-emprise',
}
const IDS_AVEC_PAS = { ...IDS, traitPas: 'x-trait-pas', cotePas: 'x-cote-pas' }

const monter = (ids = IDS, champ = CHAMP) => render(
  <TracePlanPose vue={VUE} champ={champ} ids={ids} nom="travée" titre="Ombrière en plan" />,
)

describe('TracePlanPose — le dessin du plan', () => {
  it('un contour, une ligne par rangée, une forme par table, une cote par côté', () => {
    monter()
    expect(screen.getAllByTestId('x-contour')).toHaveLength(1)
    expect(screen.getAllByTestId('x-rangee')).toHaveLength(3)
    expect(screen.getAllByTestId('x-table')).toHaveLength(3)
    expect(screen.getAllByTestId('x-cote')).toHaveLength(4)
  })

  it('le texte alternatif nomme l’écran et compte les formes posées', () => {
    monter()
    expect(screen.getByTestId('x-svg'))
      .toHaveAttribute('aria-label', 'Ombrière en plan — 3 travée(s) posée(s) par le moteur')
  })

  it('sans identifiants de pas, aucune cote de pas n’est tracée', () => {
    monter()
    expect(screen.queryByTestId('x-trait-pas')).not.toBeInTheDocument()
    expect(screen.queryByTestId('x-cote-pas')).not.toBeInTheDocument()
  })

  it('avec les identifiants de pas, le pas MESURÉ est coté', () => {
    monter(IDS_AVEC_PAS)
    expect(screen.getByTestId('x-trait-pas')).toBeInTheDocument()
    expect(screen.getByTestId('x-cote-pas').textContent).toBe(formatCote(5))
  })
})

describe('TracePlanPose — la ligne d’emprise', () => {
  it('reprend l’emprise et le compte de modules du service', () => {
    monter()
    const ligne = screen.getByTestId('x-emprise')
    expect(ligne).toHaveTextContent(/3 travée\(s\) dessinée\(s\) — emprise/)
    expect(ligne).toHaveTextContent(/18 module\(s\) posé\(s\) par le moteur\./)
  })

  it('compte de modules absent : « — », jamais le nombre de formes', () => {
    monter(IDS, { empriseTablesM2: 24, modules: null })
    expect(screen.getByTestId('x-emprise')).toHaveTextContent(/— module\(s\) posé\(s\) par le moteur\./)
  })
})
