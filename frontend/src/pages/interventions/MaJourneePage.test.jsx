import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import MaJourneePage from './MaJourneePage'

// jsdom n'implémente pas ResizeObserver (mesuré par certains primitifs UI) —
// polyfill local pour que l'écran se monte proprement.
beforeAll(polyfillResizeObserver)

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
vi.mock('../../api/installationsApi', async () => ({
  default: {
    // VX88 — Ma journée consomme désormais « Ma tournée » (ordre géographique).
    getMaTournee: vi.fn(),
    getInterventions: vi.fn(),
    // Fondateur 27/10/2026 — accord géolocalisation (undefined par défaut :
    // rien ne bloque dans les autres tests).
    getMonConsentementGps: vi.fn(),
    accepterConsentementGps: vi.fn(),
    ...(await import('../../test/mocksMaJournee')).panneauxRejetes(),
  },
}))

vi.mock('../../api/crmApi', () => ({
  default: { getRelances: vi.fn(() => Promise.resolve({ data: { results: [] } })) },
}))

import installationsApi from '../../api/installationsApi'
import crmApi from '../../api/crmApi'
import { polyfillResizeObserver } from '../../test/selectNatif'
import { reponseContrat } from '../../test/fixtures/contractSamples'

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

/* Fondateur 27/10/2026 — techniciens = prestataires externes : l'accord aux
   conditions d'utilisation (géolocalisation) est une condition BLOQUANTE de
   « Ma journée » ; puce de suivi discrète ; silence du suivi signalé. La
   réponse de `mon-consentement` vient du contrat committé (PACT10). */
describe('MaJourneePage — accord géolocalisation bloquant (27/10/2026)', () => {
  it("a_accepter : écran pleine page sans fermeture, puis « J'ai lu et j'accepte » rend la journée", async () => {
    const user = userEvent.setup()
    const contrat = reponseContrat('installations', 'gps_mon_consentement')
    expect(contrat.data.statut).toBe('a_accepter')
    installationsApi.getMonConsentementGps.mockResolvedValue(contrat)
    installationsApi.accepterConsentementGps.mockResolvedValue({
      data: { ...contrat.data, statut: 'actif', accepte_le: '2026-10-27T08:00:00+01:00' },
    })
    installationsApi.getMaTournee.mockResolvedValue({ data: { stops: [] } })
    render(<MemoryRouter><MaJourneePage /></MemoryRouter>)

    const ecran = await screen.findByTestId('gps-consentement-bloquant')
    expect(ecran.textContent).toContain("Conditions d'utilisation — géolocalisation pendant vos missions")
    expect(ecran.textContent).toContain("L'accès aux missions nécessite votre accord.")
    expect(screen.getByTestId('gps-notice').textContent).toContain('non encore déclaré')
    // Rien d'autre : ni la journée, ni un bouton de fermeture.
    expect(screen.queryByRole('heading', { name: 'Ma journée' })).not.toBeInTheDocument()
    expect(screen.getAllByRole('button')).toHaveLength(1)

    await user.click(screen.getByRole('button', { name: /J'ai lu et j'accepte/ }))
    expect(installationsApi.accepterConsentementGps).toHaveBeenCalledTimes(1)
    expect(await screen.findByRole('heading', { name: 'Ma journée' })).toBeInTheDocument()
    expect(screen.queryByTestId('gps-consentement-bloquant')).not.toBeInTheDocument()
    // La tournée est relue (les interventions portent l'accord).
    await waitFor(() => expect(installationsApi.getMaTournee.mock.calls.length).toBeGreaterThanOrEqual(2))
  })

  it("accord retiré : écran bloquant SANS bouton d'acceptation", async () => {
    const contrat = reponseContrat('installations', 'gps_mon_consentement')
    installationsApi.getMonConsentementGps.mockResolvedValue({
      data: { ...contrat.data, statut: 'revoque', actif: false },
    })
    installationsApi.getMaTournee.mockResolvedValue({ data: { stops: [] } })
    render(<MemoryRouter><MaJourneePage /></MemoryRouter>)
    expect(await screen.findByTestId('gps-consentement-retire')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /J'ai lu et j'accepte/ })).not.toBeInTheDocument()
  })

  it('responsable (« absent ») ou accord déjà donné : jamais bloqué', async () => {
    const contrat = reponseContrat('installations', 'gps_mon_consentement')
    for (const statut of ['absent', 'actif']) {
      installationsApi.getMonConsentementGps.mockResolvedValue({ data: { ...contrat.data, statut } })
      installationsApi.getMaTournee.mockResolvedValue({ data: { stops: [] } })
      const { unmount } = render(<MemoryRouter><MaJourneePage /></MemoryRouter>)
      await waitFor(() => expect(installationsApi.getMonConsentementGps).toHaveBeenCalled())
      expect(await screen.findByRole('heading', { name: 'Ma journée' })).toBeInTheDocument()
      expect(screen.queryByTestId('gps-consentement-bloquant')).not.toBeInTheDocument()
      unmount()
    }
  })

  it('en-tête de la fiche : « Suivi interrompu depuis N min » quand le serveur le signale', async () => {
    const user = userEvent.setup()
    installationsApi.getMaTournee.mockResolvedValue({
      data: {
        stops: [{
          id: 9, date_prevue: todayISO(), client_nom: 'Client Neuf',
          type_intervention: 'pose', statut: 'sur_site', gps_consentement: 'actif',
          gps_suivi_interrompu_depuis_min: 18,
        }],
      },
    })
    render(<MemoryRouter><MaJourneePage /></MemoryRouter>)
    await user.click(await screen.findByText('Client Neuf'))
    const signal = await screen.findByTestId('mj-suivi-interrompu')
    expect(signal.textContent).toBe('Suivi interrompu depuis 18 min')
    expect(signal.className).toContain('text-warning')
  })
})

/* ERR-TECH-MAJOURNEE-RELANCES-403 — « À faire aujourd'hui » ne demande les
   relances commerciales (GET /crm/leads/relances/ → 403 pour un Technicien) que
   si la permission servie `crm_voir` (ou le palier admin) l'autorise. */
describe('MaJourneePage — relances commerciales gatées par la permission servie', () => {
  const rendreAvec = (auth) => render(
    <Provider store={configureStore({ reducer: { auth: (s = auth) => s } })}>
      <MemoryRouter><MaJourneePage /></MemoryRouter>
    </Provider>,
  )

  it("un Technicien (sans crm_voir) n'appelle pas les relances", async () => {
    installationsApi.getMaTournee.mockResolvedValue({ data: { stops: [] } })
    rendreAvec({ role: 'normal', role_nom: 'Technicien', permissions: ['sav_voir'] })
    expect(await screen.findByRole('heading', { name: 'Ma journée' })).toBeInTheDocument()
    await waitFor(() => expect(installationsApi.getMaTournee).toHaveBeenCalled())
    expect(crmApi.getRelances).not.toHaveBeenCalled()
  })

  it('un porteur de crm_voir demande les relances du jour', async () => {
    installationsApi.getMaTournee.mockResolvedValue({ data: { stops: [] } })
    rendreAvec({ role: 'normal', permissions: ['crm_voir'] })
    await waitFor(() => expect(crmApi.getRelances).toHaveBeenCalledWith(
      { scope: 'today' }, expect.anything(),
    ))
  })
})
