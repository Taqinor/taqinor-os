import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { hourlyHorizonFactors, maskedHourCount } from '@rooflib/horizonEngine'

/* ============================================================================
   ACAL254 — « Heures masquées » de l'onglet Horizon = celles de l'atelier.
   ----------------------------------------------------------------------------
   Avant : l'écran recomptait au pas de 0,5 h sur 3 jours de repère (22 pour ce
   profil) alors que l'atelier applique la matrice 12×24 de
   `horizonEngine.hourlyHorizonFactors`. Désormais l'écran importe CE moteur
   (alias `@rooflib`) et affiche `maskedHourCount` de la même matrice, en heures.
   ========================================================================== */

const layout = vi.fn()
vi.mock('../../api/calepinageApi', () => ({
  default: { calepinages: { layout: (...a) => layout(...a), horizon: vi.fn(), enregistrerLayoutCalepinage: vi.fn() } },
}))

const { default: HorizonPanel } = await import('./HorizonPanel')

const LATITUDE = 33.57
const POINTS = [
  { azimuthDeg: 0, heightDeg: 20 },
  { azimuthDeg: 120, heightDeg: 20 },
  { azimuthDeg: 240, heightDeg: 20 },
]

beforeEach(() => {
  vi.clearAllMocks()
  layout.mockResolvedValue({
    data: { roof_layout: { pin: { lat: LATITUDE, lng: -7.6 }, horizonProfile: { source: 'saisie', points: POINTS } } },
  })
})
afterEach(() => { cleanup() })

describe('ACAL254 — heures masquées = maskedHourCount de l’atelier', () => {
  it('3 points à 20° : la valeur affichée est celle du moteur partagé, en heures', async () => {
    const attendu = maskedHourCount(hourlyHorizonFactors(LATITUDE, POINTS))
    expect(attendu).toBeGreaterThan(0)
    render(<MemoryRouter><HorizonPanel calepinageId={7} /></MemoryRouter>)
    const valeur = await screen.findByTestId('cal-horizon-heures-masquees')
    await vi.waitFor(() => expect(valeur).toHaveTextContent(String(attendu)))
  })
})
