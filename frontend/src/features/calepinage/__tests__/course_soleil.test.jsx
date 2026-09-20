import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* ============================================================================
   CAL96 — LA COURSE DU SOLEIL, PAR PAN.
   ----------------------------------------------------------------------------
   Le diagramme se lit pour le pan SÉLECTIONNÉ ; les obstructions proches (CAL94
   — obstacles de toiture à hauteur saisie CAL66 + environnement CAL67, les
   deux seules sources qui voyagent dans le document) apparaissent aux BONS
   azimuts ; aucune donnée météo n'est inventée.
   ========================================================================== */

const layout = vi.fn()
vi.mock('../../../api/calepinageApi', () => ({
  default: { calepinages: { layout: (...a) => layout(...a) } },
}))

const { default: CourseSoleil } = await import('../CourseSoleil')
const { azimutHauteur, obstructionsDesObstacles, centroideDuContour } = await import('../obstructionMath')

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { cleanup() })

const rendre = (props = {}) => render(
  <MemoryRouter><CourseSoleil calepinageId={7} {...props} /></MemoryRouter>,
)

/* ── 1. La géométrie pure des obstructions ──────────────────────────────── */

describe('CAL96 — obstructionMath (moteur pur)', () => {
  it('azimutHauteur : un point plein Est donne un azimut ≈ 90°', () => {
    // ~1 km à l'est, à la même latitude.
    const pos = azimutHauteur(-7.6, 33.5, -7.6 + 0.01, 33.5, 10)
    expect(pos.azimuthDeg).toBeGreaterThan(80)
    expect(pos.azimuthDeg).toBeLessThan(100)
  })

  it('un obstacle sans hauteur saisie est écarté (il ne projette rien)', () => {
    const origine = { lng: -7.6, lat: 33.5 }
    const obstacles = [{ centerLng: -7.599, centerLat: 33.5, type: 'cheminee' }]
    expect(obstructionsDesObstacles(origine, obstacles)).toEqual([])
  })

  it('un obstacle avec hauteur saisie donne UNE obstruction, azimut/hauteur finis', () => {
    const origine = { lng: -7.6, lat: 33.5 }
    const obstacles = [{ centerLng: -7.599, centerLat: 33.5, type: 'cheminee', heightM: 1.2 }]
    const res = obstructionsDesObstacles(origine, obstacles)
    expect(res).toHaveLength(1)
    expect(Number.isFinite(res[0].azimuthDeg)).toBe(true)
    expect(Number.isFinite(res[0].elevationDeg)).toBe(true)
    expect(res[0].label).toBe('Cheminée')
  })

  it('centroideDuContour : moyenne des sommets', () => {
    const c = centroideDuContour([[0, 0], [2, 0], [2, 2], [0, 2]])
    expect(c).toEqual({ lng: 1, lat: 1 })
  })

  it('sans origine exploitable, aucune obstruction', () => {
    expect(obstructionsDesObstacles(null, [{ centerLng: 1, centerLat: 1, heightM: 2 }])).toEqual([])
  })
})

/* ── 2. L'écran ────────────────────────────────────────────────────────── */

const ZONE = {
  id: 'z1', label: 'Pan Sud',
  vertices: [[-7.601, 33.599], [-7.599, 33.599], [-7.599, 33.601], [-7.601, 33.601]],
  obstacles: [
    { id: 'o1', centerLng: -7.598, centerLat: 33.6, type: 'cheminee', heightM: 1.5 }, // à l'Est, hauteur saisie
    { id: 'o2', centerLng: -7.6005, centerLat: 33.6002, type: 'antenne' }, // sans hauteur — écarté
  ],
}

describe('CAL96 — l’écran', () => {
  it('sans repère GPS (pin), aucune course n’est tracée — le dit explicitement', async () => {
    layout.mockResolvedValue({ data: { roof_layout: { activeAreaId: 'z1', zones: [ZONE] } } })
    rendre()
    await screen.findByTestId('cal-course-soleil')
    expect(screen.getByTestId('cal-sundiagram')).toBeInTheDocument()
    expect(screen.getByText(/Latitude du site inconnue/)).toBeInTheDocument()
  })

  it('avec repère GPS, la course est tracée et les obstructions apparaissent', async () => {
    layout.mockResolvedValue({
      data: {
        roof_layout: {
          pin: { lat: 33.6, lng: -7.6 },
          activeAreaId: 'z1',
          zones: [ZONE],
        },
      },
    })
    rendre()
    await screen.findByTestId('cal-course-soleil')
    expect(screen.queryByText(/Latitude du site inconnue/)).not.toBeInTheDocument()
    // Un seul obstacle porte une hauteur saisie ⇒ UNE obstruction surimprimée.
    expect(screen.getAllByTestId('cal-sundiagram-obstruction')).toHaveLength(1)
  })

  it('aucune obstruction à hauteur saisie ⇒ le dit explicitement, rien d’inventé', async () => {
    layout.mockResolvedValue({
      data: {
        roof_layout: {
          pin: { lat: 33.6, lng: -7.6 },
          activeAreaId: 'z1',
          zones: [{ ...ZONE, obstacles: [] }],
        },
      },
    })
    rendre()
    await screen.findByTestId('cal-course-soleil')
    expect(screen.queryByTestId('cal-sundiagram-obstruction')).not.toBeInTheDocument()
    expect(screen.getByText(/Aucune obstruction proche/)).toBeInTheDocument()
  })

  it('plusieurs pans : un sélecteur change le pan affiché', async () => {
    const zoneNord = { ...ZONE, id: 'z2', label: 'Pan Nord', obstacles: [] }
    layout.mockResolvedValue({
      data: {
        roof_layout: { pin: { lat: 33.6, lng: -7.6 }, activeAreaId: 'z1', zones: [ZONE, zoneNord] },
      },
    })
    rendre()
    await screen.findByTestId('cal-course-soleil')
    expect(screen.getAllByTestId('cal-sundiagram-obstruction')).toHaveLength(1)
    fireEvent.change(screen.getByLabelText('Pan'), { target: { value: 'z2' } })
    expect(screen.queryByTestId('cal-sundiagram-obstruction')).not.toBeInTheDocument()
  })

  it('sans aucun pan tracé, le dit clairement (pas de diagramme vide muet)', async () => {
    layout.mockResolvedValue({ data: { roof_layout: { zones: [] } } })
    rendre()
    await screen.findByTestId('cal-course-soleil')
    expect(screen.getByText(/Aucun pan tracé/)).toBeInTheDocument()
  })

  it('l’horizon lointain (CAL93) est surimprimé quand le document en porte un', async () => {
    layout.mockResolvedValue({
      data: {
        roof_layout: {
          pin: { lat: 33.6, lng: -7.6 },
          activeAreaId: 'z1',
          zones: [ZONE],
          horizonProfile: {
            source: 'saisie',
            points: [{ azimuthDeg: 90, heightDeg: 8 }, { azimuthDeg: 270, heightDeg: 5 }],
            hauteurMaxDeg: 8,
          },
        },
      },
    })
    rendre()
    await screen.findByTestId('cal-course-soleil')
    expect(screen.queryByText(/Aucun horizon lointain saisi/)).not.toBeInTheDocument()
  })
})

describe('CAL96 — l’écran est ATTEIGNABLE', () => {
  it('le module déclare la route `/calepinage/:id/course-soleil` avec ses rôles', async () => {
    const { default: config } = await import('../module.config.jsx')
    const route = config.routes.find((r) => r.path === '/calepinage/:id/course-soleil')
    expect(route, 'route course-soleil absente du module').toBeTruthy()
    expect(Array.isArray(route.roles) && route.roles.length > 0).toBe(true)
  })
})
