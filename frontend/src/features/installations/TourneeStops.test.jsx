import { describe, it, expect, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'

/* APX29 — « Ma tournée » sur la carte, composant PARTAGÉ par la planification
   et « Ma journée ». On vérifie : (1) les arrêts sont numérotés DANS L'ORDRE de
   la tournée ; (2) un arrêt sans GPS n'est jamais posé sur la carte (aucune
   position inventée) mais reste dans la liste ; (3) le bouton « Itinéraire »
   utilise le lien RENVOYÉ par l'endpoint (`itineraire_url`), jamais une URL
   reconstruite ; (4) la carte n'est pas montée du tout quand aucun arrêt n'a de
   coordonnées. */

import TourneeStops, { tourneeMarkers, tourneePath, stopLabel } from './TourneeStops'

const STOPS = [
  { id: 1, client_nom: 'Client A', site_ville: 'Casablanca', gps_lat: '33.57', gps_lng: '-7.58', itineraire_url: 'https://maps.example/1' },
  { id: 2, client_nom: 'Client B', site_ville: 'Rabat' }, // sans GPS
  { id: 3, installation_reference: 'CH-003', site_ville: 'Fès', gps_lat: '34.03', gps_lng: '-5.0' },
]

afterEach(() => { cleanup() })

describe('APX29 · marqueurs de tournée (logique pure)', () => {
  it('numérote les arrêts dans l’ordre de la tournée', () => {
    const markers = tourneeMarkers(STOPS)
    expect(markers.map((m) => m.badge)).toEqual([1, 3])
    expect(markers.map((m) => m.id)).toEqual([1, 3])
    expect(markers[0].label).toBe('1. Client A')
  })

  it('exclut de la carte les arrêts sans GPS (aucune position inventée)', () => {
    expect(tourneeMarkers(STOPS).some((m) => m.id === 2)).toBe(false)
    expect(tourneeMarkers([])).toEqual([])
    expect(tourneeMarkers(null)).toEqual([])
  })

  it('le tracé suit les arrêts géolocalisés, dans l’ordre', () => {
    expect(tourneePath(STOPS)).toEqual([[33.57, -7.58], [34.03, -5]])
  })

  it('le libellé retombe sur la référence puis sur l’id', () => {
    expect(stopLabel({ installation_reference: 'CH-009' }, 2)).toBe('2. CH-009')
    expect(stopLabel({ id: 42 }, 3)).toBe('3. #42')
  })
})

describe('APX29 · rendu', () => {
  it('liste les arrêts numérotés avec le lien Itinéraire de l’endpoint', () => {
    render(<TourneeStops stops={STOPS} />)
    const liste = screen.getByTestId('tournee-liste')
    expect(liste).toHaveTextContent('Client A')
    expect(liste).toHaveTextContent('Client B')
    expect(liste).toHaveTextContent('CH-003')
    // L'arrêt sans GPS reste listé, marqué honnêtement.
    expect(liste).toHaveTextContent('sans GPS')
    const lien = screen.getByRole('link', { name: /Itinéraire vers Client A/ })
    expect(lien).toHaveAttribute('href', 'https://maps.example/1')
  })

  it('aucun arrêt géolocalisé → message honnête, pas de carte vide', () => {
    render(<TourneeStops stops={[{ id: 9, client_nom: 'Sans GPS' }]} />)
    expect(screen.getByTestId('tournee-sans-gps')).toBeInTheDocument()
    expect(screen.getByTestId('tournee-liste')).toHaveTextContent('Sans GPS')
  })

  it('showList=false (Ma journée) : la carte seule, aucune liste dupliquée', () => {
    render(<TourneeStops stops={[{ id: 9, client_nom: 'Sans GPS' }]} showList={false} />)
    expect(screen.queryByTestId('tournee-liste')).toBeNull()
    expect(screen.getByTestId('tournee-stops')).toBeInTheDocument()
  })
})
