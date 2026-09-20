import { describe, it, expect, vi, afterEach, beforeAll } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* WIR113 — page Suivi GPS terrain (XFSM23), décision de périmètre WEB-FIRST.
   Vérifie les 3 onglets, l'appel des 3 familles d'endpoints, et surtout que
   le consentement est explicite (case à cocher obligatoire) et révocable. */

function mockMatchMedia() {
  window.matchMedia = (query) => ({
    matches: false, media: query, onchange: null,
    addEventListener: () => {}, removeEventListener: () => {},
    addListener: () => {}, removeListener: () => {}, dispatchEvent: () => false,
  })
}
beforeAll(() => { if (typeof window.matchMedia !== 'function') mockMatchMedia() })

const inst = vi.hoisted(() => ({
  getGpsConsentements: vi.fn(() => Promise.resolve({
    data: [{
      id: 1, technicien: 10, technicien_nom: 'ahmed', consent_ref: 'CG-1',
      consent_recorded_at: '2026-07-18T09:00:00Z', is_active: true,
    }],
  })),
  createGpsConsentement: vi.fn(() => Promise.resolve({ data: { id: 2 } })),
  revoquerGpsConsentement: vi.fn(() => Promise.resolve({ data: {} })),
  getCarteLivePositions: vi.fn(() => Promise.resolve({ data: [] })),
  // NTMOB9 — un seul endpoint réel (`geofence-alertes/`) sert les deux
  // onglets, chacun avec ses propres filtres serveur : l'onglet Alertes ne
  // passe jamais `chantier` (il ne veut que les sorties « à traiter ») ;
  // l'onglet Historique de présence passe toujours `chantier` (+ le type
  // choisi). Le mock distingue les deux appels sur la présence de `chantier`.
  getGeofenceAlertes: vi.fn((params) => {
    if (params?.chantier) {
      const tous = [
        {
          id: 1, technicien: 10, technicien_nom: 'ahmed',
          type_franchissement: 'entree', created_at: '2026-07-18T08:00:00Z',
        },
        {
          id: 2, technicien: 10, technicien_nom: 'ahmed',
          type_franchissement: 'sortie', created_at: '2026-07-18T12:00:00Z',
        },
      ]
      const filtres = params.type_franchissement
        ? tous.filter((e) => e.type_franchissement === params.type_franchissement)
        : tous
      return Promise.resolve({ data: filtres })
    }
    return Promise.resolve({
      data: [{
        id: 5, technicien: 10, technicien_nom: 'ahmed', distance_site_km: '3.20',
        rayon_attendu_km: '1.00', created_at: '2026-07-18T10:00:00Z',
        acquittee: false, type_franchissement: 'sortie',
      }],
    })
  }),
  acquitterGeofenceAlerte: vi.fn(() => Promise.resolve({ data: {} })),
  getInstallations: vi.fn(() => Promise.resolve({
    data: [{ id: 100, reference: 'CH-2026-001' }],
  })),
}))
vi.mock('../../api/installationsApi', () => ({ default: inst }))
vi.mock('../../api/crmApi', () => ({
  default: {
    getAssignableUsers: () => Promise.resolve({ data: [{ id: 10, username: 'ahmed' }] }),
  },
}))
// Leaflet n'est pas rendu en test (jsdom sans canvas de tuiles) : la carte est
// déjà chargée en `lazy`, on stub le module pour garder le test rapide.
vi.mock('../../components/MapView', () => ({
  default: () => <div data-testid="map-view" />,
  escapeHtml: (s) => String(s ?? ''),
}))

import SuiviGpsPage from './SuiviGpsPage'

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('SuiviGpsPage (WIR113)', () => {
  it('rend les 3 onglets et charge les consentements', async () => {
    render(<SuiviGpsPage />)
    expect(screen.getByRole('tab', { name: /Consentements/i })).toBeTruthy()
    expect(screen.getByRole('tab', { name: /Carte live/i })).toBeTruthy()
    expect(screen.getByRole('tab', { name: /Alertes géofence/i })).toBeTruthy()
    await waitFor(() => expect(inst.getGpsConsentements).toHaveBeenCalled())
    expect(await screen.findByTestId('consentement-1')).toBeTruthy()
  })

  it('affiche un consentement actif et propose de le révoquer', async () => {
    render(<SuiviGpsPage />)
    const row = await screen.findByTestId('consentement-1')
    expect(row.textContent).toContain('ahmed')
    expect(row.textContent).toContain('Actif')
    expect(screen.getByRole('button', { name: /Révoquer/i })).toBeTruthy()
  })

  it("refuse d'enregistrer un consentement sans confirmation explicite", async () => {
    const user = userEvent.setup()
    render(<SuiviGpsPage />)
    await screen.findByTestId('consentement-1')
    await user.click(screen.getByRole('button', { name: /Enregistrer un consentement/i }))
    const select = await screen.findByLabelText('Technicien')
    await user.selectOptions(select, '10')
    await user.click(screen.getByRole('button', { name: /^Enregistrer$/i }))
    expect(inst.createGpsConsentement).not.toHaveBeenCalled()
    expect(screen.getByRole('alert').textContent).toMatch(/accord explicite/i)
  })

  it('enregistre le consentement une fois la confirmation cochée', async () => {
    const user = userEvent.setup()
    render(<SuiviGpsPage />)
    await screen.findByTestId('consentement-1')
    await user.click(screen.getByRole('button', { name: /Enregistrer un consentement/i }))
    await user.selectOptions(await screen.findByLabelText('Technicien'), '10')
    await user.click(screen.getByRole('checkbox'))
    await user.click(screen.getByRole('button', { name: /^Enregistrer$/i }))
    await waitFor(() => expect(inst.createGpsConsentement).toHaveBeenCalledWith(
      expect.objectContaining({ technicien: 10 })))
  })

  it('charge la carte live et les alertes de géofence sur leurs onglets', async () => {
    const user = userEvent.setup()
    render(<SuiviGpsPage />)
    await screen.findByTestId('consentement-1')

    await user.click(screen.getByRole('tab', { name: /Carte live/i }))
    await waitFor(() => expect(inst.getCarteLivePositions).toHaveBeenCalled())

    await user.click(screen.getByRole('tab', { name: /Alertes géofence/i }))
    await waitFor(() => expect(inst.getGeofenceAlertes).toHaveBeenCalledWith(
      expect.objectContaining({ type_franchissement: 'sortie' })))
    const alerte = await screen.findByTestId('alerte-5')
    expect(alerte.textContent).toContain('À traiter')

    await user.click(screen.getByRole('button', { name: /Acquitter/i }))
    await waitFor(() => expect(inst.acquitterGeofenceAlerte).toHaveBeenCalledWith(5))
  })

  it('Historique de présence : choisir un chantier charge les franchissements réels du serveur (NTMOB9)', async () => {
    const user = userEvent.setup()
    render(<SuiviGpsPage />)
    await screen.findByTestId('consentement-1')

    await user.click(screen.getByRole('tab', { name: /Historique de présence/i }))
    await waitFor(() => expect(inst.getInstallations).toHaveBeenCalled())

    await user.selectOptions(screen.getByLabelText('Chantier'), '100')
    await waitFor(() => expect(inst.getGeofenceAlertes)
      .toHaveBeenCalledWith(expect.objectContaining({ chantier: '100' })))

    // `type_franchissement` est un champ RÉEL journalisé serveur (NTMOB9),
    // jamais dérivé côté écran à partir des positions brutes.
    const entree = await screen.findByTestId('presence-1-entree')
    expect(entree.textContent).toContain('ahmed')
    expect(entree.textContent).toContain('Entrée')
    const sortie = await screen.findByTestId('presence-2-sortie')
    expect(sortie.textContent).toContain('Sortie')
  })

  it('Historique de présence : le filtre type de franchissement interroge le serveur', async () => {
    const user = userEvent.setup()
    render(<SuiviGpsPage />)
    await screen.findByTestId('consentement-1')
    await user.click(screen.getByRole('tab', { name: /Historique de présence/i }))
    await user.selectOptions(screen.getByLabelText('Chantier'), '100')
    await screen.findByTestId('presence-1-entree')

    await user.selectOptions(screen.getByLabelText('Type de franchissement'), 'sortie')
    await waitFor(() => expect(inst.getGeofenceAlertes).toHaveBeenCalledWith(
      expect.objectContaining({ chantier: '100', type_franchissement: 'sortie' })))
    expect(screen.queryByTestId('presence-1-entree')).not.toBeInTheDocument()
    expect(screen.getByTestId('presence-2-sortie')).toBeInTheDocument()
  })
})
