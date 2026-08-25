/* L-DESSIN (fondateur 25/08/2026) — le dessin du client DOIT être visible dans
   la fiche lead. Ce test est la garde : il échoue si quelqu'un reprend le
   contour en simple badge/booléen, la régression exacte qui a fait dire au
   fondateur « i still do not receive the drawing ». */
import { describe, it, expect, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { initState } from '../draftCore'
import TraceToitClient from './TraceToitClient'
import SectionSite from './SectionSite'

afterEach(cleanup)

// Carré ≈ 20 m de côté à Casablanca, dans l'ordre d'axes de `Lead.roof_outline`.
const CONTOUR = [
  [33.589, -7.603],
  [33.589, -7.602784],
  [33.58918, -7.602784],
  [33.58918, -7.603],
]
const EPINGLE = { lat: 33.58909, lng: -7.602892 }

describe('TraceToitClient', () => {
  it('DESSINE le contour du client (polygone SVG réel, pas un badge)', () => {
    const { container } = render(<TraceToitClient contour={CONTOUR} epingle={EPINGLE} />)
    const polygone = container.querySelector('.lw-trace-toit-forme polygon')
    expect(polygone).toBeTruthy()
    // Le polygone porte 4 sommets — les vrais points du client, pas une forme
    // par défaut.
    expect(polygone.getAttribute('points').trim().split(/\s+/)).toHaveLength(4)
    expect(screen.getByText(/4 points tracés/)).toBeTruthy()
    expect(screen.getByRole('img', { name: /Contour du toit tracé par le client/ })).toBeTruthy()
  })

  it('mesure la surface sur les sommets réels et pointe la carte sur le repère', () => {
    render(<TraceToitClient contour={CONTOUR} epingle={EPINGLE} />)
    // ~400 m² : on épingle l'ordre de grandeur (le chiffre exact est testé
    // dans traceToit.test.mjs), donc jamais un « 0 m² » ni une valeur absente.
    expect(screen.getByText(/≈ \d{3} m² au sol/)).toBeTruthy()
    const lien = screen.getByRole('link', { name: /Voir sur la carte/ })
    expect(lien.getAttribute('href')).toBe(
      `https://www.google.com/maps?q=${EPINGLE.lat},${EPINGLE.lng}`)
  })

  it('avec le repère SEUL : le dit explicitement, sans dessiner de forme', () => {
    const { container } = render(<TraceToitClient contour={null} epingle={EPINGLE} />)
    expect(container.querySelector('polygon')).toBeNull()
    expect(screen.getByText(/aucun contour tracé/i)).toBeTruthy()
    expect(screen.getByRole('link', { name: /Voir sur la carte/ })).toBeTruthy()
  })

  it('sans toit du tout : rend RIEN (jamais un cadre vide)', () => {
    const { container } = render(<TraceToitClient contour={null} epingle={null} />)
    expect(container.querySelector('.lw-trace-toit')).toBeNull()
  })

  it('un contour malformé ne fabrique aucune forme', () => {
    const { container } = render(
      <TraceToitClient contour={[[33.589, -7.603], [33.589, -7.602]]} epingle={null} />)
    expect(container.querySelector('.lw-trace-toit')).toBeNull()
  })
})

describe('SectionSite — « Toiture & site » montre le tracé du client', () => {
  // Même construction que SectionsRender.test.jsx (état RÉEL du moteur), avec
  // les champs SERVEUR posés par le webhook site — jamais un état bricolé.
  const etat = (server) => ({ ...initState({ mode: 'create', currentUserId: 1 }), server })

  it('rend le dessin quand le lead porte roof_outline', () => {
    const { container } = render(
      <SectionSite
        state={etat({ roof_outline: CONTOUR, roof_point: EPINGLE })}
        setField={() => {}}
      />)
    expect(container.querySelector('.lw-trace-toit-forme polygon')).toBeTruthy()
    expect(screen.getByText(/Toit dessiné par le client/)).toBeTruthy()
  })

  it('ne montre rien de plus sur un lead sans toit repéré', () => {
    const { container } = render(
      <SectionSite state={etat({})} setField={() => {}} />)
    expect(container.querySelector('.lw-trace-toit')).toBeNull()
  })
})
