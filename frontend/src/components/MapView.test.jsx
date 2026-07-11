import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import MapView from './MapView'
import { ThemeProvider } from '../design/ThemeProvider'

/* VX195 — MapView.jsx n'avait ni role/aria-label sur le conteneur Leaflet, ni
   moyen d'atteindre les marqueurs au clavier (Leaflet gère ses marqueurs en
   impératif, hors de l'arbre d'accessibilité React). On vérifie : (1) le
   conteneur porte role="application" + aria-label FR annonçant le nombre de
   points ; (2) une liste de boutons parallèle expose chaque marqueur comme un
   <button> focalisable ; (3) cliquer ce bouton déclenche le même
   onMarkerClick que le marqueur Leaflet. */

const MARKERS = [
  { id: 1, lat: 33.5, lng: -7.6, label: 'Lead A' },
  { id: 2, lat: 34.0, lng: -6.8, label: 'Chantier B' },
]

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

function renderMap(props = {}) {
  return render(
    <ThemeProvider>
      <MapView markers={MARKERS} {...props} />
    </ThemeProvider>,
  )
}

describe('MapView (VX195 — accessibilité clavier)', () => {
  it('porte role="application" et un aria-label FR annonçant le nombre de points', () => {
    renderMap()
    const map = screen.getByRole('application', { name: 'Carte, 2 points' })
    expect(map).toBeInTheDocument()
  })

  it('expose une liste de boutons parallèle, un par marqueur', async () => {
    const user = userEvent.setup()
    renderMap()
    const summary = screen.getByText('Liste des points de la carte (accès clavier)')
    await user.click(summary)
    expect(screen.getByRole('button', { name: 'Lead A' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Chantier B' })).toBeInTheDocument()
  })

  it('cliquer un bouton de la liste appelle onMarkerClick avec le bon marqueur', async () => {
    const user = userEvent.setup()
    const onMarkerClick = vi.fn()
    renderMap({ onMarkerClick })
    const summary = screen.getByText('Liste des points de la carte (accès clavier)')
    await user.click(summary)
    await user.click(screen.getByRole('button', { name: 'Chantier B' }))
    expect(onMarkerClick).toHaveBeenCalledWith(expect.objectContaining({ id: 2, label: 'Chantier B' }))
  })

  it('n\'affiche pas la liste clavier quand il n\'y a aucun marqueur', () => {
    renderMap({ markers: [] })
    expect(screen.queryByText('Liste des points de la carte (accès clavier)')).not.toBeInTheDocument()
    expect(screen.getByRole('application', { name: 'Carte, 0 points' })).toBeInTheDocument()
  })
})
