import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* ============================================================================
   CALX121 — LE PANNEAU « COUPE ».
   ----------------------------------------------------------------------------
   CE QUE CE TEST TIENT :
     * le document `roof_layout` est lu via `GET .../layout/` (MÊME source que
       `CourseSoleil.jsx`), jamais `builderApi` ;
     * un pan sans géométrie posée (moins de deux rangées) affiche « non
       calculée » avec le motif exact — jamais un dessin inventé ;
     * un pan sans géométrie du tout affiche l'état vide, jamais la coupe ;
     * une géométrie complète dessine le SVG et publie les cinq valeurs
       (inclinaison, pas, hauteur hors-tout, rayon solaire, longueur d'ombre).
   ========================================================================== */

const layout = vi.fn()
vi.mock('../../../api/calepinageApi', () => ({
  default: { calepinages: { layout: (...a) => layout(...a) } },
}))

const { default: OngletCoupeRangees } = await import('./OngletCoupeRangees')

const rendre = () => render(
  <MemoryRouter><OngletCoupeRangees calepinageId={1} /></MemoryRouter>,
)

/** Trois panneaux d'une même rangée, à `cy` fixe (mêmes coordonnées que le
 *  document `roof_layout`, ENU mètres). */
function rangee(cy) {
  return [-1, 0, 1].map((cx) => ({ cx, cy }))
}

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { cleanup() })

describe('CALX121 — géométrie complète : la coupe est dessinée', () => {
  it('publie les cinq valeurs lues de la géométrie déjà posée', async () => {
    layout.mockResolvedValue({
      data: {
        roof_layout: {
          activeAreaId: 'z1',
          pin: { lat: 33.5, lng: -7.6 },
          zones: [{
            id: 'z1',
            geometry: {
              tiltDeg: 13,
              flush: false,
              azimuthDeg: 180,
              panels: [...rangee(0), ...rangee(-2.5)],
            },
          }],
        },
      },
    })
    rendre()

    expect(await screen.findByTestId('cal-coupe-svg')).toBeInTheDocument()
    expect(screen.getByTestId('cal-coupe-inclinaison')).toHaveTextContent('13')
    expect(screen.getByTestId('cal-coupe-pas')).toHaveTextContent('2,5')
    expect(screen.getByTestId('cal-coupe-hauteur')).toBeInTheDocument()
    expect(screen.getByTestId('cal-coupe-rayon-solaire-valeur')).toBeInTheDocument()
    expect(screen.getByTestId('cal-coupe-longueur-ombre')).toBeInTheDocument()
    // Deux rangées dessinées, à l'échelle du pas mesuré.
    expect(screen.getByTestId('cal-coupe-rangee-0')).toBeInTheDocument()
    expect(screen.getByTestId('cal-coupe-rangee-1')).toBeInTheDocument()
  })

  it('n’avertit pas d’un ombrage entre rangées quand le pas mesuré l’évite', async () => {
    layout.mockResolvedValue({
      data: {
        roof_layout: {
          activeAreaId: 'z1',
          pin: { lat: 33.5, lng: -7.6 },
          zones: [{
            id: 'z1',
            geometry: {
              tiltDeg: 13,
              flush: false,
              azimuthDeg: 180,
              // Pas large : bien au-delà de l'empreinte + l'ombre de conception.
              panels: [...rangee(0), ...rangee(-4)],
            },
          }],
        },
      },
    })
    rendre()
    await screen.findByTestId('cal-coupe-svg')
    expect(screen.queryByTestId('cal-coupe-alerte-ombrage')).not.toBeInTheDocument()
  })
})

describe('CALX121 — géométrie insuffisante : état « non calculée », jamais un dessin inventé', () => {
  it('une seule rangée posée : le pas n’est pas mesurable', async () => {
    layout.mockResolvedValue({
      data: {
        roof_layout: {
          activeAreaId: 'z1',
          pin: { lat: 33.5, lng: -7.6 },
          zones: [{ id: 'z1', geometry: { tiltDeg: 13, flush: false, azimuthDeg: 180, panels: rangee(0) } }],
        },
      },
    })
    rendre()

    expect(await screen.findByTestId('cal-coupe-non-calculee')).toHaveTextContent('Moins de deux rangées')
    expect(screen.queryByTestId('cal-coupe-svg')).not.toBeInTheDocument()
  })

  it('aucun pan tracé : état vide, jamais « non calculée »', async () => {
    layout.mockResolvedValue({
      data: { roof_layout: { activeAreaId: null, pin: null, zones: [] } },
    })
    rendre()

    expect(await screen.findByTestId('cal-coupe-vide')).toBeInTheDocument()
    expect(screen.queryByTestId('cal-coupe-svg')).not.toBeInTheDocument()
    expect(screen.queryByTestId('cal-coupe-non-calculee')).not.toBeInTheDocument()
  })
})

describe('CALX121 — le serveur refuse la lecture', () => {
  it('affiche le message d’erreur, jamais une coupe muette', async () => {
    layout.mockRejectedValue(new Error('réseau'))
    rendre()

    expect(await screen.findByRole('alert')).toHaveTextContent('Impossible de charger la conception.')
  })
})
