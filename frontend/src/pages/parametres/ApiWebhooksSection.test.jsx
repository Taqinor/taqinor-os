import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

const ok = (data) => Promise.resolve({ data })

vi.mock('../../api/publicapiApi', () => ({
  default: {
    getKeys: vi.fn(() => ok({ results: [] })),
    getWebhooks: vi.fn(() => ok({ results: [] })),
    getCatalogue: vi.fn(() => ok({ scopes: [], events: [] })),
    getPlan: vi.fn(() => ok(null)),
    getChangelog: vi.fn(() => ok({ results: [
      { id: 1, titre: 'Nouveau tableau de bord', corps: 'Un cockpit direction.', version: '2.4', type: 'feature', breaking: false, date: '2026-07-18T09:00:00Z' },
      { id: 2, titre: 'Correction export', corps: '', version: '2.3', type: 'fix', breaking: false, date: '2026-07-10T09:00:00Z' },
    ] })),
    // NTAPI39/40 — tableau de bord de monitoring, chargé au montage par
    // MonitoringDashboard (toujours présent sur cet écran, indépendant de
    // l'onglet actif — répondre ici évite un rejet non géré dans CETTE suite).
    getMonitoring: vi.fn(() => ok({
      appels: { total: 0, taux_erreur_pct: 0, latence_moyenne_ms: null, latence_p95_ms: null },
      top_endpoints: [],
      webhooks: {
        succes_24h: 0, echecs_24h: 0, echecs_definitifs_24h: 0,
        webhooks_actifs: 0, webhooks_desactives: 0,
      },
      jobs: { en_cours: 0, en_echec: 0, derniers: [] },
    })),
  },
}))

import publicapiApi from '../../api/publicapiApi'
import ApiWebhooksSection from './ApiWebhooksSection'

describe('ApiWebhooksSection — onglet Nouveautés (WIR158)', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('affiche les dernières entrées du changelog public', async () => {
    render(<ApiWebhooksSection />)
    // `findBy*` attend 1 s par défaut : l'écran enchaîne 5 chargements mockés
    // avant de rendre l'onglet Nouveautés et dépasse ce délai dès que la suite
    // tourne en parallèle (rouge reproductible sur `vitest run src/pages/parametres`).
    expect(await screen.findByText('Nouveau tableau de bord', {}, { timeout: 5000 }))
      .toBeInTheDocument()
    expect(screen.getByText('Correction export')).toBeInTheDocument()
    expect(screen.getByText('Nouveauté')).toBeInTheDocument()
    expect(screen.getByText('Correctif')).toBeInTheDocument()
    expect(publicapiApi.getChangelog).toHaveBeenCalled()
  })
})

describe('ApiWebhooksSection — Monitoring des intégrations (NTAPI40)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    publicapiApi.getMonitoring.mockResolvedValue({
      data: {
        appels: { total: 4820, taux_erreur_pct: 3.2, latence_moyenne_ms: 180, latence_p95_ms: 640 },
        top_endpoints: [
          { chemin: '/api/public/v1/leads/', appels: 3000, erreurs: 60, taux_erreur_pct: 2.0, latence_moyenne_ms: 150 },
        ],
        webhooks: {
          succes_24h: 40, echecs_24h: 2, echecs_definitifs_24h: 1,
          webhooks_actifs: 3, webhooks_desactives: 1,
        },
        jobs: { en_cours: 1, en_echec: 0, derniers: [
          { id: 9, type: 'import', entite: 'leads', statut: 'en_cours', progression_pct: 42, traites: 210, erreurs: 0 },
        ] },
      },
    })
  })

  it('affiche les quotas/appels/latence réels', async () => {
    render(<ApiWebhooksSection />)
    expect(await screen.findByText('4820')).toBeInTheDocument()
    expect(screen.getByText('3.2 %')).toBeInTheDocument()
    expect(screen.getByText('180 ms')).toBeInTheDocument()
    expect(screen.getByText('640 ms')).toBeInTheDocument()
    expect(publicapiApi.getMonitoring).toHaveBeenCalledWith(7)
  })

  it('affiche la santé des webhooks et les jobs récents', async () => {
    render(<ApiWebhooksSection />)
    await screen.findByText('4820')
    expect(screen.getByText('40 succès')).toBeInTheDocument()
    expect(screen.getByText('1 échec(s) définitif(s)')).toBeInTheDocument()
    expect(screen.getByText('import — leads')).toBeInTheDocument()
  })

  it('recharge sur une autre fenêtre (7/30/90 j)', async () => {
    render(<ApiWebhooksSection />)
    await screen.findByText('4820')
    fireEvent.click(screen.getByRole('radio', { name: '30 j' }))
    await waitFor(() => expect(publicapiApi.getMonitoring).toHaveBeenCalledWith(30))
  })
})
