import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest'
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

// getMaTournee est désormais partagé par les deux blocs (VX42 + VX226) : sans
// reset, ses compteurs d'appels s'accumulent d'un test à l'autre et cassent les
// assertions toHaveBeenCalledTimes. clearAllMocks vide l'historique d'appels
// mais PRÉSERVE les implémentations (les stubs `rejected` des panneaux).
beforeEach(() => vi.clearAllMocks())

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

/* VX226 — priorité (déjà annotée/triée côté serveur, jamais rendue avant) +
   fraîcheur (bouton Actualiser + refetch throttlé sur visibilitychange). */
describe('MaJourneePage (VX226)', () => {
  it('une intervention urgente porte une puce « Urgente » distincte du rang', async () => {
    // VX88 — Ma journée consomme getMaTournee (stops), pas getInterventions.
    installationsApi.getMaTournee.mockResolvedValue({
      data: {
        stops: [{
          id: 4,
          date_prevue: todayISO(),
          client_nom: 'Client Urgent',
          type_intervention: 'depannage',
          statut: 'a_preparer',
          priorite: 'urgente',
        }],
      },
    })
    render(<MemoryRouter><MaJourneePage /></MemoryRouter>)

    await waitFor(() => expect(screen.getByText('Client Urgent')).toBeInTheDocument())
    expect(screen.getByText('Urgente')).toBeInTheDocument()
  })

  it('une intervention priorité normale ne porte aucune puce (silence visuel)', async () => {
    installationsApi.getMaTournee.mockResolvedValue({
      data: {
        stops: [{
          id: 5,
          date_prevue: todayISO(),
          client_nom: 'Client Normal',
          type_intervention: 'maintenance',
          statut: 'a_preparer',
          priorite: 'normale',
        }],
      },
    })
    render(<MemoryRouter><MaJourneePage /></MemoryRouter>)

    await waitFor(() => expect(screen.getByText('Client Normal')).toBeInTheDocument())
    expect(screen.queryByText('Urgente')).not.toBeInTheDocument()
    expect(screen.queryByText('Haute')).not.toBeInTheDocument()
  })

  it('le bouton Actualiser relance le chargement au clic', async () => {
    const user = userEvent.setup()
    installationsApi.getMaTournee.mockResolvedValue({ data: { stops: [] } })
    render(<MemoryRouter><MaJourneePage /></MemoryRouter>)

    await waitFor(() => expect(installationsApi.getMaTournee).toHaveBeenCalledTimes(1))
    await user.click(screen.getByRole('button', { name: 'Actualiser' }))
    await waitFor(() => expect(installationsApi.getMaTournee).toHaveBeenCalledTimes(2))
  })

  it('un retour sur l’onglet après ≥ 2 min déclenche un refetch silencieux (visibilitychange)', async () => {
    installationsApi.getMaTournee.mockResolvedValue({ data: { stops: [] } })
    render(<MemoryRouter><MaJourneePage /></MemoryRouter>)
    await waitFor(() => expect(installationsApi.getMaTournee).toHaveBeenCalledTimes(1))

    const realNow = Date.now
    try {
      Date.now = () => realNow() + 3 * 60 * 1000 // + 3 min (>= throttle 2 min)
      Object.defineProperty(document, 'visibilityState', { value: 'visible', configurable: true })
      document.dispatchEvent(new Event('visibilitychange'))
      await waitFor(() => expect(installationsApi.getMaTournee).toHaveBeenCalledTimes(2))
    } finally {
      Date.now = realNow
    }
  })

  it('un retour sur l’onglet avant 2 min ne déclenche PAS de refetch (throttle)', async () => {
    installationsApi.getMaTournee.mockResolvedValue({ data: { stops: [] } })
    render(<MemoryRouter><MaJourneePage /></MemoryRouter>)
    await waitFor(() => expect(installationsApi.getMaTournee).toHaveBeenCalledTimes(1))

    Object.defineProperty(document, 'visibilityState', { value: 'visible', configurable: true })
    document.dispatchEvent(new Event('visibilitychange'))
    // Laisse le temps à un éventuel (mauvais) refetch de partir, puis vérifie
    // qu'il n'y en a PAS eu (throttle < 2 min depuis le fetch initial).
    await new Promise((r) => setTimeout(r, 20))
    expect(installationsApi.getMaTournee).toHaveBeenCalledTimes(1)
  })
})
