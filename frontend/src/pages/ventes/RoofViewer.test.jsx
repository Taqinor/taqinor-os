import { describe, it, expect, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import RoofViewer from './RoofViewer'

/* QG11 — RoofViewer : rendu LECTURE SEULE du `roof_layout` stocké sur un devis.
   On vérifie (1) le rendu d'un plan à partir d'une géométrie sérialisée,
   (2) la dégradation propre en état vide sans plan, (3) le résumé des zones. */

afterEach(() => cleanup())

// Layout minimal valide (forme serializeLayout de roofPro11) : une zone carrée.
function sampleLayout() {
  return {
    version: 1,
    pin: { lat: 33.5, lng: -7.6 },
    outline: [[33.5, -7.6]],
    billKwh: 8400,
    activeAreaId: 'z1',
    zones: [
      {
        id: 'z1',
        label: 'Toit principal',
        vertices: [
          [-7.6000, 33.5000],
          [-7.5995, 33.5000],
          [-7.5995, 33.5005],
          [-7.6000, 33.5005],
        ],
        obstacles: [
          { id: 'o1', centerLng: -7.5998, centerLat: 33.5002, lengthM: 2, widthM: 2 },
        ],
        roofType: 'flat',
        pitchDeg: 15,
        facingAzimuthDeg: 180,
        facingManual: false,
        neededPanels: 12,
        neededAuto: true,
      },
    ],
  }
}

describe('RoofViewer — géométrie / dégradation', () => {
  it('rend le plan SVG dès qu\'une zone est dessinable (≥ 3 sommets)', () => {
    render(<RoofViewer layout={sampleLayout()} />)
    expect(screen.getByTestId('roofviewer-svg')).toBeTruthy()
  })

  it('dégrade en état vide pour un layout vide ou une zone < 3 sommets', () => {
    // Layout sans zone → état vide.
    const { unmount } = render(<RoofViewer layout={{ zones: [] }} />)
    expect(screen.getByTestId('roofviewer-empty')).toBeTruthy()
    unmount()
    // Zone dégénérée (< 3 sommets) → état vide, pas de SVG.
    render(<RoofViewer layout={{ zones: [{ id: 'x', vertices: [[-7.6, 33.5]] }] }} />)
    expect(screen.getByTestId('roofviewer-empty')).toBeTruthy()
    expect(screen.queryByTestId('roofviewer-svg')).toBeNull()
  })
})

describe('RoofViewer — rendu', () => {
  it('rend le plan SVG + le résumé des zones à partir du layout', () => {
    render(<RoofViewer layout={sampleLayout()} />)
    // Le SVG du plan est présent.
    expect(screen.getByTestId('roofviewer-svg')).toBeTruthy()
    // Le résumé mentionne le total de panneaux + le libellé de la zone.
    // (le texte « 12 panneaux » apparaît au total ET par zone → getAllByText).
    expect(screen.getAllByText(/12 panneaux/).length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText(/1 zone/)).toBeTruthy()
    expect(screen.getByText('Toit principal')).toBeTruthy()
    // Le type de toit et l'orientation cardinale sont restitués.
    expect(screen.getByText(/Toit plat/)).toBeTruthy()
    expect(screen.getByText(/Sud/)).toBeTruthy()
  })

  it('affiche un état vide explicite sans plan ni image (dégradation propre)', () => {
    render(<RoofViewer layout={null} />)
    expect(screen.getByTestId('roofviewer-empty')).toBeTruthy()
    expect(screen.getByText(/Aucun plan de toiture enregistré/)).toBeTruthy()
    // Aucun SVG de plan n'est rendu dans l'état vide.
    expect(screen.queryByTestId('roofviewer-svg')).toBeNull()
  })

  it('affiche l\'aperçu image quand imageUrl est fourni', () => {
    render(<RoofViewer layout={null} imageUrl="blob:mock" />)
    const img = screen.getByAltText('Aperçu 3D de la toiture')
    expect(img).toBeTruthy()
    expect(img.getAttribute('src')).toBe('blob:mock')
  })
})
