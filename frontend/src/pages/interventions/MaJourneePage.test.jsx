import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import MaJourneePage from './MaJourneePage'

// jsdom n'implémente pas ResizeObserver (mesuré par certains primitifs UI) —
// polyfill local pour que l'écran se monte proprement.
beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

// NB : la factory `vi.mock` est hoistée — pas de référence à une variable
// top-level déclarée après. On construit la liste du jour directement ici.
function todayISO() {
  const d = new Date()
  const tz = d.getTimezoneOffset() * 60000
  return new Date(d - tz).toISOString().slice(0, 10)
}

// NB : la fiche (InterventionFlowSheet) monte TOUS les panneaux F5-F19 même si
// un seul onglet est visible (Radix Tabs garde les <TabsContent> inactifs
// montés). Chaque panneau appelle son endpoint de chargement au montage — on
// les stub en rejet gracieux (chaque panneau a son propre `.catch`) pour
// éviter un throw synchrone sur une méthode manquante du mock.
// `vi.mock` est hoistée au-dessus des `const` du module : on définit `rejected`
// via `vi.hoisted` pour qu'il soit initialisé avant l'exécution de la factory.
const { rejected } = vi.hoisted(() => ({
  rejected: () => Promise.reject(new Error('non mocké')),
}))
vi.mock('../../api/installationsApi', () => ({
  default: {
    // VX88 — Ma journée consomme désormais « Ma tournée » (ordre géographique).
    getMaTournee: vi.fn(),
    getInterventions: vi.fn(),
    getPreparation: vi.fn(rejected),
    getPhotos: vi.fn(rejected),
    getSerials: vi.fn(rejected),
    getConsommation: vi.fn(rejected),
    getMemos: vi.fn(rejected),
    getReserves: vi.fn(rejected),
    getSafety: vi.fn(rejected),
    getToolReturn: vi.fn(rejected),
    getCode: vi.fn(rejected),
    compteRenduUrl: vi.fn(() => ''),
  },
}))

import installationsApi from '../../api/installationsApi'

/* VX42 — Terrain un-tap : boutons directs Appeler/Itinéraire sur chaque
   carte (masqués si la donnée manque), FAB « Photo rapide » (masqué sans
   intervention), rail d'onglets icône+libellé avec bandeau « Prochaine
   action » dans la fiche. */
describe('MaJourneePage (VX42)', () => {
  it('affiche Appeler + Itinéraire quand contact/GPS sont présents, et le FAB', async () => {
    installationsApi.getMaTournee.mockResolvedValue({
      data: {
        stops: [{
          id: 1,
          date_prevue: todayISO(),
          client_nom: 'Client Un',
          type_intervention: 'installation',
          statut: 'a_preparer',
          site_ville: 'Casablanca',
          contact_site_telephone: '+212 6 12 34 56 78',
          gps_lat: 33.5731,
          gps_lng: -7.5898,
        }],
      },
    })
    render(<MemoryRouter><MaJourneePage /></MemoryRouter>)

    await waitFor(() => expect(screen.getByText('Client Un')).toBeInTheDocument())

    expect(screen.getByRole('link', { name: /Appeler le contact sur site/ })).toHaveAttribute(
      'href', 'tel:+212612345678')
    expect(screen.getByRole('link', { name: /Ouvrir l'itinéraire/ }))
      .toHaveAttribute('href', expect.stringContaining('33.5731,-7.5898'))

    // FAB « Photo rapide » : présent dès qu'il y a au moins une intervention.
    expect(screen.getByRole('button', { name: 'Photo rapide' })).toBeInTheDocument()
  })

  it('masque Appeler/Itinéraire quand aucun contact ni GPS/ville ne sont renseignés', async () => {
    installationsApi.getMaTournee.mockResolvedValue({
      data: {
        stops: [{
          id: 2,
          date_prevue: todayISO(),
          client_nom: 'Client Deux',
          type_intervention: 'maintenance',
          statut: 'a_preparer',
        }],
      },
    })
    render(<MemoryRouter><MaJourneePage /></MemoryRouter>)

    await waitFor(() => expect(screen.getByText('Client Deux')).toBeInTheDocument())

    expect(screen.queryByRole('link', { name: /Appeler/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /itinéraire/i })).not.toBeInTheDocument()
  })

  it("masque le FAB « Photo rapide » quand il n'y a aucune intervention aujourd'hui", async () => {
    installationsApi.getMaTournee.mockResolvedValue({ data: { stops: [] } })
    render(<MemoryRouter><MaJourneePage /></MemoryRouter>)

    await waitFor(() => expect(
      screen.getByText("Aucune intervention aujourd'hui")).toBeInTheDocument())
    expect(screen.queryByRole('button', { name: 'Photo rapide' })).not.toBeInTheDocument()
  })

  it('la fiche ouvre sur un rail d’onglets icône+libellé avec le bandeau « Prochaine action »', async () => {
    const user = userEvent.setup()
    installationsApi.getMaTournee.mockResolvedValue({
      data: {
        stops: [{
          id: 3,
          date_prevue: todayISO(),
          client_nom: 'Client Trois',
          type_intervention: 'installation',
          statut: 'sur_site',
        }],
      },
    })
    render(<MemoryRouter><MaJourneePage /></MemoryRouter>)

    await waitFor(() => expect(screen.getByText('Client Trois')).toBeInTheDocument())
    await user.click(screen.getByText('Client Trois'))

    // Rail d'onglets : icône + libellé court (pas seulement l'icône).
    expect(await screen.findByTestId('mj-tab-rail')).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /Photos/ })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /Trajet/ })).toBeInTheDocument()

    // Bandeau « Prochaine action » : statut sur_site → « Photos ».
    const banner = screen.getByTestId('mj-next-action')
    expect(banner).toHaveTextContent('Prochaine action')
    expect(banner).toHaveTextContent('photos obligatoires')
  })
})
