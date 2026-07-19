import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import CarteView from './CarteView'

/* FG37/LB29 — CarteView pilote Leaflet en impératif via components/MapView
   (N85) : on le mocke ici (comme ForecastView.test.jsx mocke LeadCard) plutôt
   que de faire tourner Leaflet réel sous jsdom (fragile, aucun autre test du
   repo n'exerce MapView réel — mesuré, aucun `components/MapView` mocké
   n'existe encore ailleurs, cette lane est la première). Concentré sur la
   logique propre à CarteView : empty states, repli tokenisé, câblage
   hoveredId RETIRÉ (LB29 — cf. commentaire dans CarteView.jsx). */

vi.mock('../../../../components/MapView', () => ({
  default: ({ markers, onMarkerClick }) => (
    <div data-testid="mapview">
      {markers.map((m) => (
        <button key={m.id} type="button" data-color={m.color} onClick={() => onMarkerClick(m)}>
          {m.label}
        </button>
      ))}
    </div>
  ),
  escapeHtml: (s) => String(s ?? ''),
}))

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('CarteView (FG37/LB29)', () => {
  it('affiche un EmptyState quand la liste de leads est vide', () => {
    render(<CarteView leads={[]} onOpenLead={vi.fn()} />)
    expect(screen.getByText('Aucun lead')).toBeInTheDocument()
    expect(screen.queryByTestId('mapview')).not.toBeInTheDocument()
  })

  it('rend la carte (mockée) avec un marqueur par lead géolocalisé', () => {
    render(
      <CarteView
        leads={[
          { id: 1, nom: 'Alami', stage: 'NEW', gps_lat: '33.5', gps_lng: '-7.6' },
          { id: 2, nom: 'Sans GPS', stage: 'CONTACTED' },
        ]}
        onOpenLead={vi.fn()}
      />,
    )
    expect(screen.getByTestId('mapview')).toBeInTheDocument()
    expect(screen.getByText('Alami')).toBeInTheDocument()
    // Le bandeau des leads sans GPS liste séparément les non-géolocalisés.
    expect(screen.getByText(/1 lead sans GPS/)).toBeInTheDocument()
  })

  it('LB29 — repli tokenisé pour une étape inconnue (jamais un hex brut)', () => {
    render(
      <CarteView
        leads={[{ id: 3, nom: 'ÉtapeInconnue', stage: 'NE_EXISTE_PAS', gps_lat: '33.5', gps_lng: '-7.6' }]}
        onOpenLead={vi.fn()}
      />,
    )
    const marker = screen.getByText('ÉtapeInconnue')
    expect(marker.getAttribute('data-color')).toBe('var(--muted-foreground)')
  })

  it('LB29 — le bouton « sans GPS » ouvre la fiche au clic, sans câblage hoveredId mort (aria-current retiré)', async () => {
    const onOpenLead = vi.fn()
    render(
      <CarteView
        leads={[{ id: 4, nom: 'Bennani', stage: 'NEW' }]}
        onOpenLead={onOpenLead}
      />,
    )
    const summary = screen.getByText(/1 lead sans GPS/)
    await userEvent.click(summary)
    const btn = screen.getByRole('button', { name: /Bennani/ })
    expect(btn).not.toHaveAttribute('aria-current')
    await userEvent.click(btn)
    expect(onOpenLead).toHaveBeenCalledWith(expect.objectContaining({ id: 4 }))
  })
})
