import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* ============================================================================
   CAL63 — LA TRANSFORMATION, PUIS L'ÉCRAN QUI S'EN SERT.
   ----------------------------------------------------------------------------
   La tâche exige un « test unitaire de la transformation » : la moitié haute
   de ce fichier appelle les fonctions PURES sans monter React. La moitié basse
   tient les deux promesses de l'écran : le calage est PERSISTÉ puis RELU, et
   l'échelle vient d'une DISTANCE SAISIE — sans elle, rien n'est enregistré et
   le refus se pose SOUS le champ fautif.
   ========================================================================== */

const layout = vi.fn()
const enregistrerLayout = vi.fn()
vi.mock('../../../api/calepinageApi', () => ({
  default: {
    calepinages: {
      layout: (...a) => layout(...a),
      enregistrerLayout: (...a) => enregistrerLayout(...a),
    },
  },
}))

const {
  default: PlanImporteCalage, echelleDepuisDeuxPoints, appliquerCalage,
  calerContour, aimanter,
} = await import('../PlanImporteCalage')

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { cleanup() })

/* ── 1. LA TRANSFORMATION, PURE ────────────────────────────────────────── */

describe('CAL63 — l’échelle vient de la distance SAISIE, jamais d’une estimation', () => {
  it('deux points distants de 4 unités pour 10 m réels : 2,5 m par unité', () => {
    const mesure = echelleDepuisDeuxPoints([0, 0], [4, 0], 10)
    expect(mesure.echelle).toBeCloseTo(2.5, 10)
    expect(mesure.distancePlan).toBeCloseTo(4, 10)
    expect(mesure.source).toBe('saisie')
  })

  it('sans distance réelle saisie : AUCUNE échelle — jamais un repli sur 1', () => {
    expect(echelleDepuisDeuxPoints([0, 0], [4, 0], null)).toBeNull()
    expect(echelleDepuisDeuxPoints([0, 0], [4, 0], '')).toBeNull()
    expect(echelleDepuisDeuxPoints([0, 0], [4, 0], 0)).toBeNull()
    expect(echelleDepuisDeuxPoints([0, 0], [4, 0], -3)).toBeNull()
  })

  it('deux points confondus, ou un point manquant : aucune échelle', () => {
    expect(echelleDepuisDeuxPoints([2, 2], [2, 2], 10)).toBeNull()
    expect(echelleDepuisDeuxPoints(null, [4, 0], 10)).toBeNull()
    expect(echelleDepuisDeuxPoints([0, 0], undefined, 10)).toBeNull()
  })
})

describe('CAL63 — rotation, échelle puis translation, dans cet ordre', () => {
  it('rotation de 90° autour de l’origine', () => {
    const [x, y] = appliquerCalage([1, 0], { rotationDeg: 90 })
    expect(x).toBeCloseTo(0, 10)
    expect(y).toBeCloseTo(1, 10)
  })

  it('rotation autour d’un PIVOT choisi : le pivot ne bouge pas', () => {
    const pivot = [5, 5]
    expect(appliquerCalage(pivot, { pivot, rotationDeg: 37 })[0]).toBeCloseTo(5, 10)
    expect(appliquerCalage(pivot, { pivot, rotationDeg: 37 })[1]).toBeCloseTo(5, 10)
  })

  it('échelle puis translation : (2,0) ×3 puis +(10,1) = (16,1)', () => {
    const [x, y] = appliquerCalage([2, 0], { echelle: 3, translation: [10, 1] })
    expect(x).toBeCloseTo(16, 10)
    expect(y).toBeCloseTo(1, 10)
  })

  it('composition complète : 90°, ×2, translation (1,1)', () => {
    const [x, y] = appliquerCalage([1, 0], {
      rotationDeg: 90, echelle: 2, translation: [1, 1],
    })
    expect(x).toBeCloseTo(1, 10)   // 0×2 + 1
    expect(y).toBeCloseTo(3, 10)   // 1×2 + 1
  })

  it('une composante absente est NEUTRE — elle ne déplace rien', () => {
    expect(appliquerCalage([7, -3], {})).toEqual([7, -3])
    // Une échelle nulle ou négative n'écrase pas le plan : elle est ignorée.
    expect(appliquerCalage([7, -3], { echelle: 0 })).toEqual([7, -3])
  })

  it('le contour entier suit la même transformation', () => {
    const contour = [[0, 0], [1, 0], [1, 1]]
    const cale = calerContour(contour, { echelle: 2, translation: [5, 0] })
    expect(cale).toEqual([[5, 0], [7, 0], [7, 2]])
    expect(calerContour(null, {})).toEqual([])
  })
})

describe('CAL63 — l’aimantation colle DANS la tolérance, et jamais au-delà', () => {
  const murs = [[10, 10], [0, 0]]

  it('un point à 0,3 avec une tolérance de 0,5 se colle au sommet du mur', () => {
    const r = aimanter([0.3, 0], murs, 0.5)
    expect(r.aimante).toBe(true)
    expect(r.point).toEqual([0, 0])
  })

  it('un point hors tolérance ne bouge PAS — aucun tracé tiré « pour faire propre »', () => {
    const r = aimanter([3, 0], murs, 0.5)
    expect(r.aimante).toBe(false)
    expect(r.point).toEqual([3, 0])
  })

  it('sans cible ni tolérance, le point est rendu tel quel', () => {
    expect(aimanter([3, 0], [], 0.5).aimante).toBe(false)
    expect(aimanter([3, 0], murs, 0).aimante).toBe(false)
  })
})

/* ── 2. L'ÉCRAN : persistance, relecture, refus sous le champ ──────────── */

const CONTOUR = [[0, 0], [4, 0], [4, 3]]

const rendre = (contour = CONTOUR) => render(
  <MemoryRouter>
    <PlanImporteCalage calepinageId={7} contour={contour} />
  </MemoryRouter>,
)

describe('CAL63 — l’écran cale, enregistre et relit', () => {
  it('sans plan importé, il le DIT au lieu d’afficher un calque vide', async () => {
    layout.mockResolvedValue({ data: { roof_layout: {} } })
    rendre(null)
    expect(await screen.findByTestId('cal-calage-sans-plan')).toBeInTheDocument()
  })

  it('refuse d’enregistrer sans distance réelle, SOUS le champ fautif', async () => {
    layout.mockResolvedValue({ data: { roof_layout: {} } })
    rendre()
    await screen.findByTestId('cal-calage-plan')

    fireEvent.click(screen.getByTestId('cal-calage-enregistrer'))
    expect(screen.getByTestId('cal-calage-erreur-distanceReelleM'))
      .toHaveTextContent('distance réelle')
    expect(enregistrerLayout).not.toHaveBeenCalled()
    // Et l'écran ne prétend surtout pas connaître une échelle.
    expect(screen.getByTestId('cal-calage-facteur'))
      .toHaveTextContent('aucune échelle n’est estimée')
  })

  it('enregistre le calage DANS le document de conception, échelle tracée', async () => {
    layout.mockResolvedValue({ data: { roof_layout: { version: 2, outline: [] } } })
    enregistrerLayout.mockResolvedValue({ data: { inchange: false } })
    rendre()
    await screen.findByTestId('cal-calage-plan')

    fireEvent.change(screen.getByLabelText(/Distance réelle/), { target: { value: '10' } })
    fireEvent.click(screen.getByTestId('cal-calage-enregistrer'))

    await waitFor(() => expect(enregistrerLayout).toHaveBeenCalledTimes(1))
    const [id, document] = enregistrerLayout.mock.calls[0]
    expect(id).toBe(7)
    // Le reste du document de conception est PRÉSERVÉ : on n'écrase pas la toiture.
    expect(document.version).toBe(2)
    expect(document.planImporte.calage.echelle).toBeCloseTo(2.5, 10)
    expect(document.planImporte.calage.echelle_source).toBe('saisie')
    expect(document.planImporte.calage.distanceReelleM).toBe(10)
    expect(document.planImporte.contour).toEqual(CONTOUR)
    expect(await screen.findByTestId('cal-calage-message'))
      .toHaveTextContent('rechargé tel quel')
  })

  it('RELIT le calage persisté au montage — il n’est pas perdu', async () => {
    layout.mockResolvedValue({
      data: {
        roof_layout: {
          planImporte: {
            contour: CONTOUR,
            calage: {
              translation: [3, 4], rotationDeg: 15, echelle: 2.5,
              indexA: 0, indexB: 1, distanceReelleM: 10,
            },
          },
        },
      },
    })
    render(
      <MemoryRouter><PlanImporteCalage calepinageId={7} /></MemoryRouter>,
    )
    await screen.findByTestId('cal-calage-plan')

    expect(await screen.findByLabelText(/Distance réelle/)).toHaveValue(10)
    expect(screen.getByLabelText(/Rotation/)).toHaveValue(15)
    expect(screen.getByLabelText(/Translation X/)).toHaveValue(3)
    expect(screen.getByTestId('cal-calage-facteur')).toHaveTextContent('2.5')
  })

  it('convertit le plan calé en tracé de toit', async () => {
    layout.mockResolvedValue({ data: { roof_layout: { version: 2 } } })
    enregistrerLayout.mockResolvedValue({ data: {} })
    rendre()
    await screen.findByTestId('cal-calage-plan')

    fireEvent.change(screen.getByLabelText(/Distance réelle/), { target: { value: '10' } })
    fireEvent.click(screen.getByTestId('cal-calage-convertir'))

    await waitFor(() => expect(enregistrerLayout).toHaveBeenCalledTimes(1))
    const [, document] = enregistrerLayout.mock.calls[0]
    // (0,0) est le pivot : il reste en place ; (4,0) ×2,5 devient (10,0).
    expect(document.outline[0][0]).toBeCloseTo(0, 10)
    expect(document.outline[1][0]).toBeCloseTo(10, 10)
  })
})

describe('CAL63 — l’écran est ATTEIGNABLE', () => {
  it('le module déclare la route `/calepinage/:id/plan` avec ses rôles', async () => {
    const { default: config } = await import('../module.config.jsx')
    const route = config.routes.find((r) => r.path === '/calepinage/:id/plan')
    expect(route, 'route de calage du plan absente du module').toBeTruthy()
    expect(Array.isArray(route.roles) && route.roles.length > 0).toBe(true)
  })
})
