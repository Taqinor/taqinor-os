import { describe, it, expect, vi } from 'vitest'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { render, screen } from '@testing-library/react'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { configureStore } from '@reduxjs/toolkit'
import { exempleContrat } from '../test/fixtures/contractSamples'
import {
  Component as Dashboard,
  cockpitProfile,
  leadsARelancer,
  devisQuiExpirent,
  ticketsAujourdhui,
  ticketsUrgents,
  ticketsSlaEnRetard,
  lecturesAccueil,
} from './Dashboard.jsx'

// TCH125 — la carte lit `taches/aujourdhui/` : client mocké, jamais le réseau ; le reste de l'écran est neutralisé.
const tachesApiMock = vi.hoisted(() => ({ lireAujourdhui: vi.fn() }))
vi.mock('../api/tachesApi', async (importOriginal) => ({
  ...(await importOriginal()),
  lireAujourdhui: tachesApiMock.lireAujourdhui,
}))
vi.mock('../api/axios', () => ({ default: { get: vi.fn(() => Promise.resolve({ data: [] })), post: vi.fn(() => Promise.resolve({ data: {} })) } }))
vi.mock('../api/ventesApi', () => ({ default: { getDashboardQuoteToCash: vi.fn(() => Promise.resolve({ data: {} })) } }))
vi.mock('../api/reportingApi', () => ({ default: { getDashboard: vi.fn(() => Promise.resolve({ data: {} })) } }))
vi.mock('../components/ActivityFeedWidget', () => ({ default: () => null }))
vi.mock('../components/MesEquipesCard', () => ({ default: () => null }))
vi.mock('../components/ApprobationsAttentionCard', () => ({ default: () => null }))
vi.mock('../components/PremiersPasWidget', () => ({ default: () => null }))
vi.mock('../components/DemoResumeWidget', () => ({ default: () => null }))
vi.mock('../features/uxviews/RecentEntitiesWidget', () => ({ default: () => null }))
vi.mock('../features/uxviews/FavorisWidget', () => ({ default: () => null }))
vi.mock('../features/reporting/SlaBadgeCard', () => ({ default: () => null }))

/* VX27 — Cockpit du matin : layout par rôle + bandeau « aujourd'hui ».
   On teste les fonctions PURES qui décident CE QUE chaque rôle voit (le
   « rendu conditionnel » du composant est piloté par cockpitProfile) et les
   dérivations de signaux du jour — sans monter le composant ni le store. */

// Date fixe pour des comparaisons déterministes.
const NOW = new Date('2026-07-11T09:00:00')

describe('cockpitProfile — classification de rôle (VX27)', () => {
  it('directeur/admin → vue macro', () => {
    expect(cockpitProfile({ roleNom: 'Directeur' })).toBe('directeur')
    expect(cockpitProfile({ roleNom: 'Gérant' })).toBe('directeur')
    expect(cockpitProfile({ roleTier: 'admin', roleNom: 'Peu importe' })).toBe('directeur')
  })
  it('commercial → cockpit ventes', () => {
    expect(cockpitProfile({ roleNom: 'Commercial' })).toBe('commercial')
    expect(cockpitProfile({ roleNom: 'Commercial responsable' })).toBe('commercial')
    expect(cockpitProfile({ roleNom: 'Chargé de vente' })).toBe('commercial')
  })
  it('SAV/technicien → cockpit terrain', () => {
    expect(cockpitProfile({ roleNom: 'Technicien SAV' })).toBe('sav')
    expect(cockpitProfile({ roleNom: 'Support après-vente' })).toBe('sav')
  })
  it('rôle inconnu ou vide → directeur (repli macro, comportement historique)', () => {
    expect(cockpitProfile({ roleNom: null })).toBe('directeur')
    expect(cockpitProfile({})).toBe('directeur')
    expect(cockpitProfile({ roleNom: 'Magasinier' })).toBe('directeur')
  })
  it('admin l’emporte sur un libellé « commercial »', () => {
    expect(cockpitProfile({ roleTier: 'admin', roleNom: 'Commercial' })).toBe('directeur')
  })
})

describe('leadsARelancer (VX27)', () => {
  const leads = [
    { id: 1, nom: 'A', owner: 7, relance_date: '2026-07-10' }, // hier → à relancer
    { id: 2, nom: 'B', owner: 7, relance_date: '2026-07-11' }, // aujourd'hui → à relancer
    { id: 3, nom: 'C', owner: 7, relance_date: '2026-07-20' }, // futur → non
    { id: 4, nom: 'D', owner: 7, relance_date: null },         // pas de relance → non
    { id: 5, nom: 'E', owner: 9, relance_date: '2026-07-01' }, // autre owner
    { id: 6, nom: 'F', owner: 7, relance_date: '2026-07-01', perdu: true }, // perdu → non
    { id: 7, nom: 'G', owner: 7, relance_date: '2026-07-01', is_archived: true }, // archivé → non
  ]
  it('retient les relances dues ou dépassées, non perdues/archivées', () => {
    const r = leadsARelancer(leads, { now: NOW }).map((l) => l.id)
    expect(r).toEqual([1, 2, 5])
  })
  it('scope à « mes » leads quand ownerId est fourni', () => {
    const r = leadsARelancer(leads, { ownerId: 7, now: NOW }).map((l) => l.id)
    expect(r).toEqual([1, 2])
  })
  it('liste vide / nulle ne casse pas', () => {
    expect(leadsARelancer(null, { now: NOW })).toEqual([])
    expect(leadsARelancer([], { now: NOW })).toEqual([])
  })
})

describe('devisQuiExpirent (VX27)', () => {
  const devis = [
    { id: 1, statut: 'envoye', date_validite: '2026-07-12' },   // ≤7j → oui
    { id: 2, statut: 'brouillon', date_validite: '2026-07-11' },// aujourd'hui → oui
    { id: 3, statut: 'envoye', date_validite: '2026-07-25' },   // >7j → non
    { id: 4, statut: 'accepte', date_validite: '2026-07-12' },  // clôturé → non
    { id: 5, statut: 'envoye', date_validite: null },           // sans date → non
    { id: 6, statut: 'envoye', date_validite: '2026-07-01' },   // déjà expiré → non
  ]
  it('retient les devis ouverts expirant dans la fenêtre de N jours', () => {
    const r = devisQuiExpirent(devis, { days: 7, now: NOW }).map((d) => d.id)
    expect(r).toEqual([1, 2])
  })
})

describe('tickets SAV — signaux terrain (VX27)', () => {
  const tickets = [
    { id: 1, statut: 'nouveau', priorite: 'urgente', date_ouverture: '2026-07-08' },
    { id: 2, statut: 'en_cours', priorite: 'haute', date_ouverture: '2026-07-11' },
    { id: 3, statut: 'cloture', priorite: 'urgente', date_ouverture: '2026-06-01' },
    { id: 4, statut: 'planifie', priorite: 'normale', date_ouverture: '2026-07-11' },
    { id: 5, statut: 'nouveau', priorite: 'urgente', date_ouverture: '2026-07-08', annule: true },
  ]
  it('ticketsAujourdhui = ouverts non annulés', () => {
    expect(ticketsAujourdhui(tickets).map((t) => t.id)).toEqual([1, 2, 4])
  })
  it('ticketsUrgents = haute/urgente ouverts non annulés', () => {
    expect(ticketsUrgents(tickets).map((t) => t.id)).toEqual([1, 2])
  })
  it('ticketsSlaEnRetard = tickets que le serveur déclare sla_breach (ASAV47)', () => {
    // #1 : le serveur dit sla_breach=true → compté.
    const avecSla = tickets.map((t) => (t.id === 1 ? { ...t, sla_breach: true } : t))
    const r = ticketsSlaEnRetard(avecSla, NOW).map((t) => t.id)
    expect(r).toContain(1)
    // #3 clôturé, #5 annulé → jamais late.
    expect(r).not.toContain(3)
    expect(r).not.toContain(5)
  })
})

/* ERR-ACC-ACCUEIL-403-LECTEUR : le Lecteur n'a pas droit à `crm/equipes/
   statistiques/` ni à `monitoring/configs/co2-fleet/` (IsResponsableOrAdmin) :
   la carte « Mes équipes » n'est pas montée pour lui, et ces deux lectures ne
   déclenchent jamais le toast d'erreur global. Test-du-test : retirer la garde
   `peutLireEquipes` ou `suppressErrorToast` fait échouer. */
describe('cartes gardées IsResponsableOrAdmin : accueil du Lecteur (ERR-ACC-ACCUEIL-403-LECTEUR)', () => {
  const lire = (rel) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf8')
  it("MesEquipesCard n'est monté que si le rôle peut lire les équipes", () => {
    const src = lire('./Dashboard.jsx')
    expect(src).toMatch(/useCanLireEquipesCrm\(\)/)
    expect(src).toMatch(/peutLireEquipes && \(\s*<Suspense fallback=\{null\}>\s*<MesEquipesCard \/>/)
  })
  it("ImpactPastille n'est monté (dans la Sidebar) que si le rôle peut lire le parc", () => {
    const src = lire('../components/layout/Sidebar.jsx')
    expect(src).toMatch(/peutLireParc && \(\s*<Suspense fallback=\{null\}>\s*<ImpactPastille/)
  })
  // ADRG120 — droits calculés par useDroitMetier('crm_voir') / useCanLireTableauDeBord
  // (useHasPermission.test.jsx) : Technicien (installation_*, sav_*, reporting_voir)
  // = ni CRM ni tableau ; Viewer = CRM seul ; Commercial et légacy responsable = tout.
  it('lecturesAccueil : le Technicien ne lit ni leads, ni tableau de bord, ni Mes chiffres', () => {
    expect(lecturesAccueil({ peutLireVentes: false, peutLireCrm: false, peutLireTableau: false }))
      .toEqual({ ventes: false, leads: false, reporting: false, mesChiffres: false })
    expect(lecturesAccueil({ peutLireVentes: true, peutLireCrm: true, peutLireTableau: false }))
      .toMatchObject({ leads: true, reporting: false, mesChiffres: true })
    expect(lecturesAccueil({ peutLireVentes: true, peutLireCrm: true, peutLireTableau: true }))
      .toMatchObject({ leads: true, reporting: true, mesChiffres: true })
  })
  it('les deux lectures coupent le toast global sur 403', () => {
    expect(lire('../api/monitoringApi.js')).toMatch(/co2-fleet\/', \{ params, suppressErrorToast: true \}/)
    expect(lire('../api/crmApi.js')).toMatch(/equipes\/statistiques\/', \{ suppressErrorToast: true \}/)
  })
})

/* ── TCH125 — la carte « Tâches · Aujourd'hui » du tableau de bord ───────── */
describe('Dashboard — TCH125 : carte des tâches avec taches_voir seulement', () => {
  const aujourdhui = exempleContrat('taches', 'aujourdhui')
  const vide = (s = { items: [], loading: false, error: null }) => s
  const monter = (permissions, modulesDesactives = []) => {
    const auth = { user: { id: 42, username: 'reda' }, role: 'admin', role_nom: 'Administrateur', permissions, modulesDesactives }
    const store = configureStore({
      reducer: {
        auth: (s = auth) => s,
        stock: (s = { produits: [], loading: false, error: null }) => s,
        crm: (s = { clients: [], leads: [], loading: false, error: null }) => s,
        ventes: (s = { devis: [], factures: [], loading: false, error: null }) => s,
        installations: (s = vide()) => s,
        tickets: (s = vide()) => s,
        parametres: (s = { profile: null }) => s,
      },
    })
    return render(
      <Provider store={store}>
        <MemoryRouter initialEntries={['/dashboard']}><Dashboard /></MemoryRouter>
      </Provider>,
    )
  }

  it('avec taches_voir : la carte lit taches/aujourdhui/ et s\'affiche', async () => {
    tachesApiMock.lireAujourdhui.mockReset()
    tachesApiMock.lireAujourdhui.mockResolvedValue({ data: aujourdhui })
    monter(['taches_voir'])
    expect(await screen.findByRole('region', { name: /Tâches, aujourd'hui/ })).toBeInTheDocument()
    expect(tachesApiMock.lireAujourdhui).toHaveBeenCalledTimes(1)
  })

  it('sans taches_voir : aucune carte, aucune requête Tâches', async () => {
    tachesApiMock.lireAujourdhui.mockReset()
    tachesApiMock.lireAujourdhui.mockResolvedValue({ data: aujourdhui })
    monter([])
    expect(await screen.findByRole('heading', { name: 'Tableau de bord' })).toBeInTheDocument()
    await new Promise((r) => setTimeout(r, 50))
    expect(screen.queryByRole('region', { name: /Tâches, aujourd'hui/ })).toBeNull()
    expect(tachesApiMock.lireAujourdhui).not.toHaveBeenCalled()
  })

  it('F4 revue #15 — avec taches_voir mais le module Tâches éteint pour la société : aucune carte, aucune requête Tâches', async () => {
    tachesApiMock.lireAujourdhui.mockReset()
    tachesApiMock.lireAujourdhui.mockResolvedValue({ data: aujourdhui })
    monter(['taches_voir'], ['taches'])
    expect(await screen.findByRole('heading', { name: 'Tableau de bord' })).toBeInTheDocument()
    await new Promise((r) => setTimeout(r, 50))
    expect(screen.queryByRole('region', { name: /Tâches, aujourd'hui/ })).toBeNull()
    expect(tachesApiMock.lireAujourdhui).not.toHaveBeenCalled()
  })
})
