import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* ============================================================================
   CALX118 — LA COURSE DU SOLEIL DU SITE, ENRICHIE DANS L'ATELIER.
   ----------------------------------------------------------------------------
   Le composant `CourseSoleil`, DÉJÀ inscrit au rail par CALX1, rend `SunDiagram`
   pour le pan actif SANS RECALCULER (il lit `calepinages.layout`) : ce fichier
   couvre les trois Done de la tâche — (1) sans profil d'horizon, le diagramme
   s'affiche sans remplissage et le dit ; (2) le repère du soleil suit
   `scene.sunDay`/`scene.sunHour` (contrat CALX88) ; (3) un seul composant
   « course du soleil » existe dans le registre. Les tests CAL96/CALX52
   (obstructions, hauteur de toit supposée) restent dans `course_soleil.test.jsx`.
   ========================================================================== */

const layout = vi.fn()
vi.mock('../../../api/calepinageApi', () => ({
  default: { calepinages: { layout: (...a) => layout(...a) } },
}))

const { default: CourseSoleil } = await import('../CourseSoleil')

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { cleanup() })

const rendre = (props = {}) => render(
  <MemoryRouter><CourseSoleil calepinageId={9} {...props} /></MemoryRouter>,
)

const ZONE = {
  id: 'z1',
  label: 'Pan Sud',
  vertices: [[-7.601, 33.599], [-7.599, 33.599], [-7.599, 33.601], [-7.601, 33.601]],
  obstacles: [],
}

describe('CALX118 — sans profil d’horizon, le diagramme s’affiche sans remplissage et le dit', () => {
  it('document sans horizonProfile : aucun remplissage d’horizon, message explicite', async () => {
    layout.mockResolvedValue({
      data: { roof_layout: { pin: { lat: 33.6, lng: -7.6 }, activeAreaId: 'z1', zones: [ZONE] } },
    })
    rendre()
    await screen.findByTestId('cal-course-soleil')
    expect(screen.getByTestId('cal-sundiagram')).toBeInTheDocument()
    expect(screen.getByText(/Aucun horizon lointain saisi/)).toBeInTheDocument()
  })
})

describe('CALX118 — le repère du soleil suit scene.sunDay/scene.sunHour', () => {
  it('document sans `scene` : le repère suit le défaut NOMMÉ (solstice d’hiver, midi)', async () => {
    layout.mockResolvedValue({
      data: { roof_layout: { pin: { lat: 33.6, lng: -7.6 }, activeAreaId: 'z1', zones: [ZONE] } },
    })
    rendre()
    await screen.findByTestId('cal-course-soleil')
    const mention = screen.getByTestId('cal-course-soleil-scene')
    expect(mention).toHaveTextContent('solstice d’hiver, midi')
    expect(mention).toHaveTextContent('aucun instant enregistré')
    // Midi au solstice d'hiver, à cette latitude, le soleil est au-dessus de l'horizon.
    expect(screen.getByTestId('cal-sundiagram-soleil-courant')).toBeInTheDocument()
  })

  it('document AVEC `scene` : le repère suit l’instant enregistré, pas le défaut', async () => {
    layout.mockResolvedValue({
      data: {
        roof_layout: {
          pin: { lat: 33.6, lng: -7.6 },
          activeAreaId: 'z1',
          zones: [ZONE],
          scene: { sunDay: 172, sunHour: 14.5 },
        },
      },
    })
    rendre()
    await screen.findByTestId('cal-course-soleil')
    const mention = screen.getByTestId('cal-course-soleil-scene')
    expect(mention).toHaveTextContent('jour 172')
    expect(mention).toHaveTextContent('14.5 h')
    expect(mention).not.toHaveTextContent('aucun instant enregistré')
    expect(screen.getByTestId('cal-sundiagram-soleil-courant')).toBeInTheDocument()
  })

  it('soleil sous l’horizon à l’instant enregistré (nuit) : aucun repère tracé, le dit', async () => {
    layout.mockResolvedValue({
      data: {
        roof_layout: {
          pin: { lat: 33.6, lng: -7.6 },
          activeAreaId: 'z1',
          zones: [ZONE],
          scene: { sunDay: 355, sunHour: 2 }, // 2 h du matin, solstice d'hiver : nuit
        },
      },
    })
    rendre()
    await screen.findByTestId('cal-course-soleil')
    expect(screen.queryByTestId('cal-sundiagram-soleil-courant')).not.toBeInTheDocument()
    expect(screen.getByTestId('cal-course-soleil-scene')).toHaveTextContent('sous l’horizon')
  })

  it('sans repère GPS (latitude inconnue) : aucun repère de soleil tracé malgré `scene`', async () => {
    layout.mockResolvedValue({
      data: { roof_layout: { activeAreaId: 'z1', zones: [ZONE], scene: { sunDay: 172, sunHour: 12 } } },
    })
    rendre()
    await screen.findByTestId('cal-course-soleil')
    expect(screen.queryByTestId('cal-sundiagram-soleil-courant')).not.toBeInTheDocument()
  })
})

describe('CALX118 — un seul composant « course du soleil » existe dans le registre', () => {
  it('atelier/onglets.js ne porte qu’UNE entrée `course-soleil`', async () => {
    const { ONGLETS } = await import('../atelier/onglets')
    const entrees = ONGLETS.filter((o) => o.cle === 'course-soleil')
    expect(entrees).toHaveLength(1)
  })
})
