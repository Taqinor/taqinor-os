import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
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

  /* T5 (suite d'ACAL1640) — la barre du soleil porte l'année de dessin du script (2028, bissextile) et sa phrase d'heure
     légale la dit ; la course du soleil disait « 2026-06-21, année en cours » pour le MÊME jour 172 : une seule date. */
  it('T5 — la course du soleil et la phrase d’heure légale de la barre disent la même date', async () => {
    const { default: HeureLegale } = await import('./HeureLegale')
    const barre = document.createElement('div')
    barre.innerHTML = '<input id="rp9-sun-hour" value="14"><input id="rp9-sun-date" type="date" value="2028-06-20">'
    document.body.appendChild(barre)
    espions.layout.mockResolvedValue({ data: { roof_layout: {
      pin: { lat: 33.6, lng: -7.6 }, zones: [ZONE], scene: { sunDay: 172, sunHour: 14 } } } })
    render(<MemoryRouter><HeureLegale calepinageId={7} /><CourseSoleil calepinageId={7} /></MemoryRouter>)
    await screen.findByTestId('cal-course-soleil')
    expect(document.getElementById('rp9-sun-legal')).toHaveTextContent('calculé pour le 20 juin 2028')
    const scene = screen.getByTestId('cal-course-soleil-scene')
    expect(scene).toHaveTextContent('jour 172 de l’année (2028-06-20)')
    expect(scene).not.toHaveTextContent('année en cours')
    barre.remove()
  })

  it('T5 — le champ de la barre écrit APRÈS le montage (puis changé sans événement) : les deux phrases suivent la même année', async () => {
    const { default: HeureLegale } = await import('./HeureLegale')
    espions.layout.mockResolvedValue({ data: { roof_layout: {
      pin: { lat: 33.6, lng: -7.6 }, zones: [ZONE], scene: { sunDay: 172, sunHour: 14 } } } })
    render(<MemoryRouter><HeureLegale calepinageId={7} /><CourseSoleil calepinageId={7} /></MemoryRouter>)
    const scene = await screen.findByTestId('cal-course-soleil-scene')
    expect(scene).toHaveTextContent(`(${new Date().getFullYear()}-`) // champ absent : l'année en cours
    const barre = document.createElement('div')
    barre.innerHTML = '<input id="rp9-sun-hour" value="14"><input id="rp9-sun-date" type="date" value="2028-06-20">'
    document.body.appendChild(barre) // le script crée la barre après le montage
    await waitFor(() => expect(screen.getByTestId('cal-course-soleil-scene')).toHaveTextContent('(2028-06-20)'))
    await waitFor(() => expect(document.getElementById('rp9-sun-legal')).toHaveTextContent('20 juin 2028'))
    document.getElementById('rp9-sun-date').value = '2032-06-20' // écriture programmatique : aucun événement
    await waitFor(() => expect(screen.getByTestId('cal-course-soleil-scene')).toHaveTextContent('(2032-06-20)'), { timeout: 4000 })
    await waitFor(() => expect(document.getElementById('rp9-sun-legal')).toHaveTextContent('20 juin 2032'), { timeout: 4000 })
    barre.remove()
  })

  it('lecture du document en échec : message d’erreur, pas d’écran vide muet', async () => {
    espions.layout.mockRejectedValue(new Error('500'))
    rendre()
    expect(await screen.findByText('Impossible de charger la conception.')).toBeInTheDocument()
  })

  // ACAL1447 — un pan SANS `buildingId` lit le bâtiment de la convention de l'atelier (`bat-sans-id`) :
  // la hauteur saisie est employée et dite ; « supposée » seulement sans hauteur saisie.
  it('pan sans buildingId + hauteur saisie : hauteur du bâtiment, pas supposée', async () => {
    const buildings = [{ id: 'bat-sans-id', hauteurM: 6, source: 'mesurée au télémètre' }]
    espions.layout.mockResolvedValue({ data: { roof_layout: { pin: { lat: 33.6, lng: -7.6 }, zones: [ZONE], buildings } } })
    rendre()
    await screen.findByTestId('cal-course-soleil')
    expect(screen.getByTestId('cal-course-soleil-hauteur-toit-provenance'))
      .toHaveTextContent('hauteur du bâtiment : 6 m (mesurée au télémètre)')
    cleanup()
    espions.layout.mockResolvedValue({ data: { roof_layout: { pin: { lat: 33.6, lng: -7.6 }, zones: [ZONE] } } })
    rendre()
    await screen.findByTestId('cal-course-soleil')
    expect(screen.getByTestId('cal-course-soleil-hauteur-toit-provenance')).toHaveTextContent(/supposée à 6 m/)
  })

  // ACAL1444 — rendu dans un panneau de ≈ 270 px : libellés à ≥ 12 px RENDUS, diagramme ≥ 200 px de haut,
  // axe vertical gradué 0/30/60/90°. Mutant : viewBox fixe 640 × 260 ⇒ 11 px × 270/640 ≈ 4,6 px, 110 px de haut.
  it('dans un panneau de 270 px : libellés rendus à 12 px au moins, plus haut, axe gradué en degrés', async () => {
    const largeurRendue = 270
    const espion = vi.spyOn(Element.prototype, 'getBoundingClientRect').mockImplementation(function rect() {
      const l = this.dataset?.testid === 'cal-sundiagram' ? largeurRendue : 0
      return { width: l, height: 0, top: 0, left: 0, right: l, bottom: 0, x: 0, y: 0 }
    })
    espions.layout.mockResolvedValue({ data: { roof_layout: { pin: { lat: 33.6, lng: -7.6 }, zones: [ZONE] } } })
    rendre()
    await screen.findByTestId('cal-course-soleil')
    const svg = screen.getByTestId('cal-sundiagram')
    const [, , vbL, vbH] = svg.getAttribute('viewBox').split(' ').map(Number)
    const echelle = largeurRendue / vbL
    expect(vbH * echelle).toBeGreaterThanOrEqual(200)
    for (const texte of svg.querySelectorAll('text')) {
      expect(Number(texte.getAttribute('font-size')) * echelle).toBeGreaterThanOrEqual(12)
    }
    expect(screen.getAllByTestId('cal-sundiagram-graduation').map((g) => g.textContent)).toEqual(['0°', '30°', '60°', '90°'])
    espion.mockRestore()
  })
})
