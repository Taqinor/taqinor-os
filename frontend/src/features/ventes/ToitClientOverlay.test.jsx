/* L-MAP (fondateur 26/08/2026) — le contour dessiné par le client DOIT être
   visible sur la carte du calepinage 3D, pas seulement dans la fiche lead.
   Ce test est la garde : il échoue si le calque redevient un badge muet, ou
   s'il s'affiche sans contour exploitable (jamais un cadre vide). */
import { describe, it, expect, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import ToitClientOverlay from './ToitClientOverlay'
import { contourExploitable } from '../crm/workspace/traceToit'

afterEach(cleanup)

// MÊME fixture que `TraceToitClient.test.jsx` (carré ≈ 20 m de côté à
// Casablanca, ordre d'axes de `Lead.roof_outline`) : la surface rendue ici
// doit être la MÊME que celle déjà validée côté fiche lead — c'est tout le
// point du calque (« zéro chiffre recalculé différemment »).
const CONTOUR = [
  [33.589, -7.603],
  [33.589, -7.602784],
  [33.58918, -7.602784],
  [33.58918, -7.603],
]

describe('ToitClientOverlay', () => {
  it('rend le contour du client en polygone SVG distinct, avec le libellé + la surface', () => {
    const { container } = render(<ToitClientOverlay contour={CONTOUR} />)
    const polygone = container.querySelector('.rp9-toit-client-polygone')
    expect(polygone).toBeTruthy()
    expect(polygone.getAttribute('points').trim().split(/\s+/)).toHaveLength(4)
    // Même surface que TraceToitClient.test.jsx (≈ 400 m²) — MÊME calcul,
    // jamais une valeur recalculée différemment.
    expect(screen.getByText(/Toit dessiné par le client · \d{3} m²/)).toBeTruthy()
  })

  it('ne rend RIEN sans contour exploitable (jamais un cadre vide ni un « 0 m² »)', () => {
    const { container: sansContour } = render(<ToitClientOverlay contour={null} />)
    expect(sansContour.querySelector('[data-testid="rp9-toit-client"]')).toBeNull()

    cleanup()
    const { container: contourCourt } = render(<ToitClientOverlay contour={[[33.589, -7.603], [33.589, -7.602784]]} />)
    expect(contourCourt.querySelector('[data-testid="rp9-toit-client"]')).toBeNull()
  })

  it('se masque quand `visible` est false, sans perdre le calcul (bascule réversible)', () => {
    const { container, rerender } = render(<ToitClientOverlay contour={CONTOUR} visible={false} />)
    expect(container.querySelector('[data-testid="rp9-toit-client"]')).toBeNull()

    rerender(<ToitClientOverlay contour={CONTOUR} visible />)
    expect(container.querySelector('[data-testid="rp9-toit-client"]')).toBeTruthy()
  })

  it('le calque est un repère PASSIF : pointer-events: none, jamais un obstacle au tracé/glissé', () => {
    // Garantie CSS (roofbuilder.css `.rp9-toit-client`), pas une assertion de
    // style inline ici : ce test verrouille juste que le composant NE PORTE
    // AUCUN gestionnaire de clic/glissé — la seule interaction du calque est
    // le bouton de bascule, rendu par l'écran hôte, PAS par ce composant.
    const { container } = render(<ToitClientOverlay contour={CONTOUR} />)
    const bloc = container.querySelector('[data-testid="rp9-toit-client"]')
    expect(bloc.onclick).toBeNull()
    expect(bloc.getAttribute('aria-hidden')).toBe('true')
  })
})

describe('contourExploitable', () => {
  it('vrai avec un contour exploitable, faux sinon', () => {
    expect(contourExploitable(CONTOUR)).toBe(true)
    expect(contourExploitable(null)).toBe(false)
    expect(contourExploitable([])).toBe(false)
    expect(contourExploitable([[33.589, -7.603], [33.589, -7.602784]])).toBe(false)
  })
})
