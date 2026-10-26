import { describe, it, expect, vi, afterEach, beforeAll, beforeEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* WIR113 — page Suivi GPS terrain (XFSM23), décision de périmètre WEB-FIRST.
   Vérifie les 3 onglets, l'appel des 3 familles d'endpoints, et surtout que
   le consentement est explicite (case à cocher obligatoire) et révocable. */

beforeAll(() => { if (typeof window.matchMedia !== 'function') mockMatchMedia() })

const inst = vi.hoisted(() => ({
  getGpsConsentements: vi.fn(() => Promise.resolve({
    data: [{
      id: 1, technicien: 10, technicien_nom: 'ahmed', consent_ref: 'CG-1',
      consent_recorded_at: '2026-07-18T09:00:00Z', is_active: true,
      accepte_le: null, is_acknowledged: false, statut: 'a_accepter',
      notice_version: 'v1', recepisse_cndp: '',
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
        acquittee: false, type_franchissement: 'sortie', intervention: 12,
      }],
    })
  }),
  acquitterGeofenceAlerte: vi.fn(() => Promise.resolve({ data: {} })),
  getInstallations: vi.fn(() => Promise.resolve({
    data: [{ id: 100, reference: 'CH-2026-001' }],
  })),
  // Revue chantier 26/10/2026 — tracé du jour, interventions du jour et
  // présence (forme = contrat committé, posée dans beforeEach).
  getPositionsTechniciens: vi.fn(() => Promise.resolve({
    data: [
      { id: 31, technicien: 10, technicien_nom: 'ahmed', intervention: 12, lat: '33.570000',
        lng: '-7.580000', accuracy_m: '9.00', captured_at: '2026-10-26T08:10:00+01:00',
        distance_site_km: '1.200', hors_perimetre: true },
      { id: 32, technicien: 10, technicien_nom: 'ahmed', intervention: 12, lat: '33.573150',
        lng: '-7.589800', accuracy_m: '6.00', captured_at: '2026-10-26T08:50:00+01:00',
        distance_site_km: '0.005', hors_perimetre: false },
    ],
  })),
  getInterventions: vi.fn(() => Promise.resolve({
    data: { results: [{ id: 12, installation_reference: 'CH-2026-012', technicien_nom: 'ahmed' }] },
  })),
  getPresenceIntervention: vi.fn(),
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
import { mockMatchMedia } from '../../test/matchMedia'
import { reponseContrat } from '../../test/fixtures/contractSamples'

beforeEach(() => {
  inst.getPresenceIntervention.mockResolvedValue(
    reponseContrat('installations', 'intervention_presence'))
})
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

  // ── Revue chantier 26/10/2026 ──────────────────────────────────────────
  it("dit si le technicien a donné son accord ou s'il est attendu", async () => {
    render(<SuiviGpsPage />)
    const row = await screen.findByTestId('consentement-1')
    expect(row.textContent).toContain("En attente d'accord du technicien")
    expect(row.textContent).toContain('récépissé CNDP non encore déclaré')
  })

  it('le dialogue transmet la version de la notice et le récépissé CNDP', async () => {
    const user = userEvent.setup()
    render(<SuiviGpsPage />)
    await screen.findByTestId('consentement-1')
    await user.click(screen.getByRole('button', { name: /Enregistrer un consentement/i }))
    await user.selectOptions(await screen.findByLabelText('Technicien'), '10')
    await user.type(screen.getByLabelText(/récépissé de la déclaration CNDP/i), 'D-123/2026')
    await user.click(screen.getByRole('checkbox'))
    await user.click(screen.getByRole('button', { name: /^Enregistrer$/i }))
    await waitFor(() => expect(inst.createGpsConsentement).toHaveBeenCalledWith(
      expect.objectContaining({
        technicien: 10, notice_version: 'v1', recepisse_cndp: 'D-123/2026',
      })))
  })

  it("carte live : âge des positions et tracé du jour d'un technicien", async () => {
    const user = userEvent.setup()
    const ilYa3Min = new Date(Date.now() - 3 * 60000).toISOString()
    inst.getCarteLivePositions.mockResolvedValue({
      data: [{
        id: 40, technicien: 10, technicien_nom: 'ahmed', intervention: 12,
        lat: '33.573150', lng: '-7.589800', accuracy_m: '6.00',
        captured_at: ilYa3Min, distance_site_km: '0.005', hors_perimetre: false,
      }],
    })
    try {
      render(<SuiviGpsPage />)
      await screen.findByTestId('consentement-1')
      await user.click(screen.getByRole('tab', { name: /Carte live/i }))
      const ages = await screen.findByTestId('carte-live-ages')
      expect(ages.textContent).toContain('ahmed · il y a 3 min')
      expect(screen.getByText(/plus de 15 min/)).toBeInTheDocument()

      await user.selectOptions(screen.getByLabelText('Tracé du technicien'), '10')
      await waitFor(() => expect(inst.getPositionsTechniciens).toHaveBeenCalledWith(
        expect.objectContaining({ technicien: '10', date: expect.any(String) })))
      expect((await screen.findByTestId('trace-compte')).textContent).toContain('2 relevé(s)')
    } finally {
      inst.getCarteLivePositions.mockResolvedValue({ data: [] })
    }
  })

  it('alertes : ouvertes par défaut, acquittées sur filtre, lien vers l\'intervention', async () => {
    const user = userEvent.setup()
    render(<SuiviGpsPage />)
    await screen.findByTestId('consentement-1')
    await user.click(screen.getByRole('tab', { name: /Alertes géofence/i }))
    const alerte = await screen.findByTestId('alerte-5')
    expect(alerte.querySelector('a').getAttribute('href')).toBe('/interventions?id=12')
    await user.selectOptions(screen.getByLabelText('Filtre des alertes'), 'acquittees')
    expect(screen.queryByTestId('alerte-5')).not.toBeInTheDocument()
  })

  it("Historique : temps sur site du jour calculé par le serveur (contrat)", async () => {
    const user = userEvent.setup()
    render(<SuiviGpsPage />)
    await screen.findByTestId('consentement-1')
    await user.click(screen.getByRole('tab', { name: /Historique de présence/i }))
    const ligne = await screen.findByTestId('presence-interv-12')
    expect(inst.getPresenceIntervention).toHaveBeenCalledWith(12)
    // duree_sur_site_min = 404 dans le contrat → « 6 h 44 ».
    expect(ligne.textContent).toContain('6 h 44')
    expect(ligne.textContent).toContain('positions GPS')
    expect(ligne.textContent).toContain('CH-2026-012')
  })
})
