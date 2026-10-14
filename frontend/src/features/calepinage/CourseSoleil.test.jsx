import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { espions } from '../../test/fixtures/calepinageApiMock'

/* ENF15 — l'onglet « Course du soleil » (CALX1) est MONTÉ. Le détail (obstructions,
   horizon, scène) vit dans `__tests__/course_soleil*.test.jsx` ; ici, l'onglet tel
   que le rail le monte : lecture du document, trace avec repère, aveu sans repère,
   échec de lecture dit. */

vi.mock('../../api/calepinageApi', async () => (await import('../../test/fixtures/calepinageApiMock')).apiDocument())

const { default: CourseSoleil } = await import('./CourseSoleil')

const ZONE = { id: 'z1', label: 'Pan Sud', vertices: [[-7.601, 33.599], [-7.599, 33.599], [-7.599, 33.601], [-7.601, 33.601]] }

const rendre = () => render(<MemoryRouter><CourseSoleil calepinageId={7} /></MemoryRouter>)

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { cleanup() })

describe('CourseSoleil — onglet monté', () => {
  it('avec repère GPS, le diagramme est tracé sans mention de latitude inconnue', async () => {
    espions.layout.mockResolvedValue({ data: { roof_layout: { pin: { lat: 33.6, lng: -7.6 }, zones: [ZONE] } } })
    rendre()
    await screen.findByTestId('cal-course-soleil')
    expect(screen.getByTestId('cal-sundiagram')).toBeInTheDocument()
    expect(screen.queryByText(/Latitude du site inconnue/)).not.toBeInTheDocument()
  })

  it('sans repère GPS, le dit au lieu d’inventer une course', async () => {
    espions.layout.mockResolvedValue({ data: { roof_layout: { zones: [ZONE] } } })
    rendre()
    await screen.findByTestId('cal-course-soleil')
    expect(screen.getByText(/Latitude du site inconnue/)).toBeInTheDocument()
  })

  it('lecture du document en échec : message d’erreur, pas d’écran vide muet', async () => {
    espions.layout.mockRejectedValue(new Error('500'))
    rendre()
    expect(await screen.findByText('Impossible de charger la conception.')).toBeInTheDocument()
  })
})
