import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* ODY19 — Passe SAV : vérifie, comme `crm/module.config.test.jsx` /
   `reporting/module.config.test.jsx` le font pour leur propre ajout, que le
   nouveau cockpit `/sav/cockpit` existe EN ROUTE ET en entrée de nav (premier
   item, la porte d'entrée de l'app), et que le module reste zéro-orphelin :
   chaque route déclarée a une entrée de nav correspondante (ou est un cas
   documenté d'exception — aucun ici, toutes les routes SAV sont dans le menu
   APRÈS-VENTE). */
describe('sav — module.config (ODY19)', () => {
  it('déclare /sav/cockpit en route ET en premier item du menu APRÈS-VENTE', async () => {
    const { default: config } = await import('./module.config.jsx')
    expect(config.key).toBe('sav')

    const route = config.routes.find((r) => r.path === '/sav/cockpit')
    expect(route).toBeTruthy()

    expect(config.nav.items[0].to).toBe('/sav/cockpit')
    expect(config.nav.items[0].label).toBe('Cockpit')
    expect(config.nav.items[0].roles).toEqual(['normal', 'responsable', 'admin'])
    expect(config.nav.items[0].icon).toBeTruthy()
  })

  it('zéro route orpheline : chaque route a une entrée de nav', async () => {
    const { default: config } = await import('./module.config.jsx')
    const navPaths = new Set(config.nav.items.map((i) => i.to))
    for (const r of config.routes) {
      expect(navPaths.has(r.path)).toBe(true)
    }
    // ... et réciproquement (parité totale route <-> nav pour ce module).
    const routePaths = new Set(config.routes.map((r) => r.path))
    for (const to of navPaths) {
      expect(routePaths.has(to)).toBe(true)
    }
  })
})


// ASAV100-103 — écran SAV/monitoring (D-ASAV-4 option (b)). Les réponses
// viennent des exemples COMMITTÉS que le test backend affirme (PACT10) —
// jamais un mock écrit à la main.
import ABONNEMENTS from '../../../../backend/django_core/apps/monitoring/contract_samples/abonnements_monitoring.json'
import SLA from '../../../../backend/django_core/apps/monitoring/contract_samples/sla_disponibilite.json'
import CERTIFICATS from '../../../../backend/django_core/apps/monitoring/contract_samples/certificats_carbone.json'
import PERTES from '../../../../backend/django_core/apps/monitoring/contract_samples/pertes_categorisees.json'

const vide = { count: 0, next: null, previous: null, results: [] }

const serveur = vi.hoisted(() => ({
  abonnements: null, creations: [], resiliations: [], slas: null, slaSaves: [], ecarts: [],
  certificats: { count: 0, next: null, previous: null, results: [] }, emissions: [],
  pertes: [],
}))

vi.mock('../../api/monitoringApi', () => ({
  default: {
    getConfigs: vi.fn(() => Promise.resolve({ data: { results: [
      { id: 5, installation: 87 },
    ] } })),
    getAbonnements: vi.fn(() => Promise.resolve({ data: serveur.abonnements })),
    getSlasDisponibilite: vi.fn(() => Promise.resolve({ data: serveur.slas })),
    getCertificatsCarbone: vi.fn(() => Promise.resolve({ data: serveur.certificats })),
    getPertesCategorisees: vi.fn((configId, params) => {
      serveur.pertes.push({ configId, params })
      return Promise.resolve({ data: PERTES.exemple })
    }),
    emettreCertificatCarbone: vi.fn((data) => {
      serveur.emissions.push(data)
      serveur.certificats = CERTIFICATS.exemple
      return Promise.resolve({ data: CERTIFICATS.exemple.results[0] })
    }),
    saveSlaDisponibilite: vi.fn((id, data) => {
      serveur.slaSaves.push({ id, data })
      return Promise.resolve({ data: SLA.exemple_liste.reponse.results[0] })
    }),
    getSlaEcart: vi.fn((id) => {
      serveur.ecarts.push(id)
      return Promise.resolve({ data: SLA.exemple })
    }),
    creerAbonnement: vi.fn((data) => {
      serveur.creations.push(data)
      return Promise.resolve({ data: ABONNEMENTS.exemple.results[0] })
    }),
    resilierAbonnement: vi.fn((id, motif) => {
      serveur.resiliations.push({ id, motif })
      const reponse = ABONNEMENTS.exemple_resiliation.reponse
      serveur.abonnements = { ...ABONNEMENTS.exemple, results: [reponse] }
      return Promise.resolve({ data: reponse })
    }),
  },
}))
vi.mock('../../api/installationsApi', () => ({
  default: {
    getInstallations: vi.fn(() => Promise.resolve({ data: { results: [
      { id: 87, reference: 'CHT-87', client_nom: 'Alami' },
    ] } })),
  },
}))

import SavMonitoringPage from './monitoring/SavMonitoringPage'

afterEach(() => {
  cleanup()
  serveur.creations.length = 0
  serveur.resiliations.length = 0
  serveur.slaSaves.length = 0
  serveur.ecarts.length = 0
  serveur.emissions.length = 0
  serveur.pertes.length = 0
  serveur.certificats = vide
})


describe('SavMonitoringPage — ASAV100 abonnements de supervision', () => {
  it('liste les abonnements servis, en crée un et le résilie (motif obligatoire)', async () => {
    serveur.abonnements = ABONNEMENTS.exemple
    serveur.slas = vide
    const user = userEvent.setup()
    render(<SavMonitoringPage />)

    const section = await screen.findByRole('region', { name: 'Abonnements de supervision' })
    const ligne = await within(section).findByRole('listitem')
    expect(ligne).toHaveTextContent('CHT-87 — Alami')
    expect(ligne).toHaveTextContent('Actif')
    expect(ligne).toHaveTextContent('Mensuel')

    // Création : système auto-sélectionné (un seul supervisé), montant saisi.
    await user.type(screen.getByLabelText('Montant par période (MAD)'), '150', { delay: null })
    await user.click(screen.getByRole('button', { name: "Créer l'abonnement" }))
    await waitFor(() => expect(serveur.creations).toHaveLength(1))
    expect(serveur.creations[0]).toMatchObject({
      installation_id: 87, periodicite: 'mensuel', montant: '150',
    })

    // Résiliation : le motif part au serveur, l'état revient du serveur.
    await user.click(await screen.findByRole('button', { name: 'Résilier' }))
    await user.type(screen.getByLabelText('Motif de résiliation'), 'Client a vendu la maison.', { delay: null })
    await user.click(screen.getByRole('button', { name: 'Confirmer la résiliation' }))
    await waitFor(() => expect(serveur.resiliations).toEqual([
      { id: ABONNEMENTS.exemple.results[0].id, motif: 'Client a vendu la maison.' },
    ]))
    await waitFor(() => expect(within(section).getByRole('listitem')).toHaveTextContent('Résilié'))
    expect(screen.queryByRole('button', { name: 'Résilier' })).not.toBeInTheDocument()
  }, 60000)
})

describe('SavMonitoringPage — ASAV101 SLA de disponibilité', () => {
  it('saisit le taux garanti et affiche l’écart servi par le serveur', async () => {
    serveur.abonnements = vide
    serveur.slas = SLA.exemple_liste.reponse
    const user = userEvent.setup()
    render(<SavMonitoringPage />)

    const section = await screen.findByRole('region', { name: 'SLA de disponibilité' })
    const ligne = await within(section).findByRole('listitem')
    expect(ligne).toHaveTextContent('CHT-87 — Alami')

    // Le système a déjà un SLA : l'enregistrement le MODIFIE (PATCH, id servi).
    await user.type(within(section).getByLabelText('Taux de disponibilité garanti (%)'), '97', { delay: null })
    await user.click(within(section).getByRole('button', { name: 'Enregistrer le SLA' }))
    await waitFor(() => expect(serveur.slaSaves).toHaveLength(1))
    expect(serveur.slaSaves[0]).toMatchObject({
      id: SLA.exemple_liste.reponse.results[0].id,
      data: { installation: 87, disponibilite_garantie_pct: '97' },
    })

    await user.click(within(section).getByRole('button', { name: "Calculer l'écart" }))
    await waitFor(() => expect(serveur.ecarts).toEqual([SLA.exemple_liste.reponse.results[0].id]))
    expect(await within(section).findByText('Sous la garantie')).toBeInTheDocument()
    expect(ligne).toHaveTextContent(SLA.exemple.libelle_indicateur)
    expect(ligne).toHaveTextContent(/456,50/)
  }, 60000)
})
describe('SavMonitoringPage — ASAV102 registre des certificats carbone', () => {
  it('émet un certificat (tCO₂ calculées serveur) et l’affiche au registre', async () => {
    serveur.abonnements = vide
    serveur.slas = vide
    serveur.certificats = vide
    const user = userEvent.setup()
    render(<SavMonitoringPage />)

    const section = await screen.findByRole('region', { name: 'Certificats carbone' })
    expect(await within(section).findByText('Aucun certificat émis')).toBeInTheDocument()

    await user.type(within(section).getByLabelText('Début de période'), '2026-01-01', { delay: null })
    await user.type(within(section).getByLabelText('Fin de période'), '2026-06-30', { delay: null })
    await user.click(within(section).getByRole('button', { name: 'Émettre le certificat' }))
    await waitFor(() => expect(serveur.emissions).toEqual([
      { installation_id: 87, periode_debut: '2026-01-01', periode_fin: '2026-06-30' },
    ]))
    // Aucune tCO₂ envoyée par l'écran : c'est le serveur qui la calcule.
    expect(serveur.emissions[0]).not.toHaveProperty('tco2_evitees')

    const ligne = await within(section).findByRole('listitem')
    expect(ligne).toHaveTextContent(CERTIFICATS.exemple.results[0].reference)
    expect(ligne).toHaveTextContent('CHT-87 — Alami')
    expect(ligne).toHaveTextContent(/3,402/)
  }, 60000)
})
describe('SavMonitoringPage — ASAV103 pertes catégorisées', () => {
  it('affiche les pertes servies par catégorie, « non mesurable » pour une catégorie null', async () => {
    serveur.abonnements = vide
    serveur.slas = vide
    render(<SavMonitoringPage />)

    const section = await screen.findByRole('region', { name: 'Pertes catégorisées' })
    // Un seul système supervisé : sélectionné d'office → la route est appelée.
    await waitFor(() => expect(serveur.pertes.length).toBeGreaterThan(0))
    expect(serveur.pertes.at(-1)).toEqual({ configId: '5', params: { window_days: '365' } })
    await waitFor(() => expect(section).toHaveTextContent('Salissure'))
    expect(section).toHaveTextContent(/4,20 %/)
    expect(section).toHaveTextContent(/2,74 %/)
    expect(section).toHaveTextContent('non mesurable')
    expect(PERTES.exemple.ombrage_pct).toBeNull()
  }, 60000)
})