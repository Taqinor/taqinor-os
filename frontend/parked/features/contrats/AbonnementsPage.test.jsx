import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* PACT138 — Abonnements : plans, options, paliers d'usage, compteurs. NTSUB1-4
   (`apps/contrats`) livraient déjà les 4 ressources SANS AUCUN écran. Vérifie
   que l'écran liste chaque ressource et que chaque onglet crée bien sa
   ressource avec le bon payload. `../../api/axios` est mocké (les appels de
   AbonnementsPage.jsx passent par lui directement, pas par contratsApi.js
   pour les endpoints NTSUB) ; `contratsApi` ne fournit ici que
   `getPlansRecurrents` (déjà existant, réutilisé). */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
  }
})

const { apiGet, apiPost } = vi.hoisted(() => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(() => Promise.resolve({ data: { id: 99 } })),
}))

vi.mock('../../api/axios', () => ({
  default: { get: (...args) => apiGet(...args), post: (...args) => apiPost(...args) },
}))

// WIR251 — import CSV compteurs (NTSUB31) + export xlsx catalogue (NTSUB21).
// `vi.hoisted` : les mocks doivent exister AVANT que `vi.mock` (hoisté en
// tête de fichier par Vitest) ne les referme — même patron que apiGet/apiPost.
const { importerCompteursUsageCsv, exportCatalogueAbonnement } = vi.hoisted(() => ({
  importerCompteursUsageCsv: vi.fn(() => Promise.resolve({ data: {
    inserees: 0, mises_a_jour: 0, erreurs: [], apercu: true, ecraser: false,
    conflits: [], ecrasements: 0, refuses: [], job_id: null,
  } })),
  exportCatalogueAbonnement: vi.fn(() => Promise.resolve({
    data: new Blob(['xlsx'], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' }),
    headers: {},
  })),
}))

vi.mock('../../api/contratsApi', () => ({
  default: {
    getPlansRecurrents: () => Promise.resolve({
      data: [{ id: 5, nom: 'Mensuel' }],
    }),
    importerCompteursUsageCsv: (...args) => importerCompteursUsageCsv(...args),
    exportCatalogueAbonnement: (...args) => exportCatalogueAbonnement(...args),
  },
}))

import AbonnementsPage from './AbonnementsPage'

const PLAN = {
  id: 1, code: 'MAINT-STD', nom: 'Maintenance standard', prix_base: '500.00',
  engagement_mois: 12, actif: true,
}
const ADDON = {
  id: 2, code: 'SUPERVISION', nom: 'Supervision avancée', plan_abonnement: 1,
  prix_unitaire: '50.00', facturation: 'recurrente', facturation_display: 'Récurrente',
  actif: true,
}
const LIGNE = {
  id: 3, type_cible: 'contrat', type_cible_display: 'Contrat', cible_id: 7,
  addon: 2, quantite: 1, actif_depuis: '2026-08-01', montant_periode: '50.00',
}
const PALIER = {
  id: 4, addon: 2, plan_abonnement: null, seuil_min: '0.00', seuil_max: null,
  prix_unitaire: '10.00', mode: 'volume', mode_display: 'Volume (dernier palier atteint)',
}
const COMPTEUR = {
  id: 6, type_cible: 'contrat', type_cible_display: 'Contrat', cible_id: 7,
  code_compteur: 'interventions', periode_debut: '2026-08-01', periode_fin: '2026-08-31',
  quantite: '3.0000', source: 'manuel', source_display: 'Manuel',
}

function setupApiGet(overrides = {}) {
  apiGet.mockImplementation((url) => {
    if (url === '/contrats/plans-abonnement/') return Promise.resolve({ data: overrides.plans ?? [PLAN] })
    if (url === '/contrats/addons-abonnement/') return Promise.resolve({ data: overrides.addons ?? [ADDON] })
    if (url === '/contrats/addon-lignes/') return Promise.resolve({ data: overrides.lignes ?? [LIGNE] })
    if (url === '/contrats/paliers-usage/') return Promise.resolve({ data: overrides.paliers ?? [PALIER] })
    if (url === '/contrats/compteurs-usage/') return Promise.resolve({ data: overrides.compteurs ?? [COMPTEUR] })
    return Promise.resolve({ data: [] })
  })
}

beforeEach(() => {
  vi.clearAllMocks()
  apiPost.mockResolvedValue({ data: { id: 99 } })
  setupApiGet()
})

function renderPage() {
  return render(<MemoryRouter><ThemeProvider><AbonnementsPage /></ThemeProvider></MemoryRouter>)
}

describe('AbonnementsPage (PACT138)', () => {
  it('liste les plans, options, paliers et compteurs déjà en base', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByText('Abonnements')).toBeInTheDocument())
    await waitFor(() => expect(screen.getByText('Maintenance standard')).toBeInTheDocument())

    await userEvent.click(screen.getByRole('tab', { name: /Options/ }))
    // « Supervision avancée » apparaît à la fois dans le tableau des add-ons
    // (colonne Nom) et dans celui des rattachements (colonne Add-on, qui
    // résout le libellé du même add-on) — deux affichages légitimes, donc on
    // cible précisément le tableau des add-ons du catalogue (le premier).
    const addonsTable = (await screen.findAllByRole('table'))[0]
    expect(within(addonsTable).getByText('Supervision avancée')).toBeInTheDocument()
    expect(screen.getByText(/Contrat #7/)).toBeInTheDocument()

    await userEvent.click(screen.getByRole('tab', { name: /Paliers/ }))
    expect(await screen.findByText('10.00')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('tab', { name: /Compteurs/ }))
    expect(await screen.findByText('interventions')).toBeInTheDocument()
  })

  it('crée un plan d’abonnement depuis l’onglet Plans', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByText('Maintenance standard')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: /Nouveau plan/ }))
    fireEvent.change(await screen.findByLabelText(/^Code/), { target: { value: 'MAINT-PREM' } })
    fireEvent.change(screen.getByLabelText(/^Nom/), { target: { value: 'Maintenance premium' } })
    fireEvent.change(screen.getByLabelText(/Cadence de facturation/), { target: { value: '5' } })
    fireEvent.click(screen.getByRole('button', { name: 'Créer le plan' }))

    await waitFor(() => expect(apiPost).toHaveBeenCalledWith('/contrats/plans-abonnement/', {
      code: 'MAINT-PREM', nom: 'Maintenance premium', plan_recurrent: 5,
    }))
  })

  it('crée un add-on rattaché à un plan depuis l’onglet Options', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByText('Maintenance standard')).toBeInTheDocument())
    await userEvent.click(screen.getByRole('tab', { name: /Options/ }))

    fireEvent.click(screen.getByRole('button', { name: /Nouvel add-on/ }))
    fireEvent.change(await screen.findByLabelText(/^Code/), { target: { value: 'VISITE-SUP' } })
    fireEvent.change(screen.getByLabelText(/^Nom/), { target: { value: 'Visite supplémentaire' } })
    fireEvent.click(screen.getByRole('button', { name: "Créer l'add-on" }))

    await waitFor(() => expect(apiPost).toHaveBeenCalledWith('/contrats/addons-abonnement/', {
      code: 'VISITE-SUP', nom: 'Visite supplémentaire', facturation: 'recurrente',
    }))
  })

  it('crée un rattachement d’add-on depuis l’onglet Options', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByText('Maintenance standard')).toBeInTheDocument())
    await userEvent.click(screen.getByRole('tab', { name: /Options/ }))

    fireEvent.click(screen.getByRole('button', { name: /Nouveau rattachement/ }))
    fireEvent.change(await screen.findByLabelText(/^Add-on/), { target: { value: '2' } })
    fireEvent.change(screen.getByLabelText(/ID de la cible/), { target: { value: '9' } })
    fireEvent.click(screen.getByRole('button', { name: 'Créer le rattachement' }))

    await waitFor(() => expect(apiPost).toHaveBeenCalledWith('/contrats/addon-lignes/', expect.objectContaining({
      type_cible: 'contrat', cible_id: 9, addon: 2, quantite: 1,
    })))
  })

  it('crée un palier d’usage depuis l’onglet Paliers', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByText('Maintenance standard')).toBeInTheDocument())
    await userEvent.click(screen.getByRole('tab', { name: /Paliers/ }))

    fireEvent.click(await screen.findByRole('button', { name: /Nouveau palier/ }))
    fireEvent.change(await screen.findByLabelText(/^Cible/), { target: { value: 'addon' } })
    fireEvent.change(screen.getByLabelText(/^Add-on/), { target: { value: '2' } })
    fireEvent.change(screen.getByLabelText(/Prix unitaire de la tranche/), { target: { value: '15' } })
    fireEvent.click(screen.getByRole('button', { name: 'Créer le palier' }))

    await waitFor(() => expect(apiPost).toHaveBeenCalledWith('/contrats/paliers-usage/', {
      seuil_min: 0, prix_unitaire: 15, mode: 'volume', addon: 2,
    }))
  })

  it('enregistre un relevé de compteur depuis l’onglet Compteurs', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByText('Maintenance standard')).toBeInTheDocument())
    await userEvent.click(screen.getByRole('tab', { name: /Compteurs/ }))

    fireEvent.click(await screen.findByRole('button', { name: /Nouveau relevé/ }))
    fireEvent.change(await screen.findByLabelText(/ID de la cible/), { target: { value: '7' } })
    fireEvent.change(screen.getByLabelText(/Code du compteur/), { target: { value: 'appels_api' } })
    fireEvent.change(screen.getByLabelText(/Début de période/), { target: { value: '2026-08-01' } })
    fireEvent.change(screen.getByLabelText(/Fin de période/), { target: { value: '2026-08-31' } })
    fireEvent.click(screen.getByRole('button', { name: 'Enregistrer le relevé' }))

    await waitFor(() => expect(apiPost).toHaveBeenCalledWith('/contrats/compteurs-usage/', {
      type_cible: 'contrat', cible_id: 7, code_compteur: 'appels_api',
      periode_debut: '2026-08-01', periode_fin: '2026-08-31', quantite: 0, source: 'manuel',
    }))
  })

  // WIR251 — import CSV en deux temps (aperçu sans écriture → confirmation
  // avec case « écraser » explicite, envoyée seulement si cochée).
  it('WIR251 — aperçu du CSV puis confirme avec « écraser » coché', async () => {
    importerCompteursUsageCsv
      .mockResolvedValueOnce({ data: {
        inserees: 0, mises_a_jour: 0, erreurs: [], apercu: true, ecraser: false,
        conflits: [{ ligne: 2, cible_id: 7, ecrasements: 1, remplissages: 0 }],
        ecrasements: 0, refuses: [], job_id: null,
      } })
      .mockResolvedValueOnce({ data: {
        inserees: 0, mises_a_jour: 1, erreurs: [], apercu: false, ecraser: true,
        conflits: [], ecrasements: 1, refuses: [], job_id: 42,
      } })

    renderPage()
    await waitFor(() => expect(screen.getByText('Maintenance standard')).toBeInTheDocument())
    await userEvent.click(screen.getByRole('tab', { name: /Compteurs/ }))

    await userEvent.click(await screen.findByRole('button', { name: /Importer \(CSV\)/i }))
    const dialog = await screen.findByRole('dialog')
    const csv = 'cible_id,code_compteur,periode_debut,periode_fin,quantite\n7,interventions,2026-08-01,2026-08-31,5'
    const file = new File([csv], 'compteurs.csv', { type: 'text/csv' })
    await userEvent.upload(within(dialog).getByLabelText('Fichier CSV'), file)

    const apercuBtn = await screen.findByRole('button', { name: 'Aperçu' })
    await waitFor(() => expect(apercuBtn).not.toBeDisabled())
    await userEvent.click(apercuBtn)

    await waitFor(() => expect(importerCompteursUsageCsv).toHaveBeenNthCalledWith(1, {
      contenu: csv, apercu: true,
    }))
    expect(await within(dialog).findByText(/1 conflit\(s\)/)).toBeInTheDocument()

    // Case « écraser » n'apparaît (et n'est cochable) qu'APRÈS l'aperçu.
    await userEvent.click(within(dialog).getByRole('checkbox'))
    await userEvent.click(within(dialog).getByRole('button', { name: /Confirmer l.import/i }))

    await waitFor(() => expect(importerCompteursUsageCsv).toHaveBeenNthCalledWith(2, {
      contenu: csv, apercu: false, ecraser: true,
    }))
  })

  it('WIR251 — n’envoie PAS « écraser » quand la case reste décochée', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByText('Maintenance standard')).toBeInTheDocument())
    await userEvent.click(screen.getByRole('tab', { name: /Compteurs/ }))

    await userEvent.click(await screen.findByRole('button', { name: /Importer \(CSV\)/i }))
    const dialog = await screen.findByRole('dialog')
    const csv = 'cible_id,code_compteur,periode_debut,periode_fin,quantite\n7,interventions,2026-08-01,2026-08-31,5'
    const file = new File([csv], 'compteurs.csv', { type: 'text/csv' })
    await userEvent.upload(within(dialog).getByLabelText('Fichier CSV'), file)

    const apercuBtn = await screen.findByRole('button', { name: 'Aperçu' })
    await waitFor(() => expect(apercuBtn).not.toBeDisabled())
    await userEvent.click(apercuBtn)

    // Aucune case cochée : « Confirmer l'import » directement, dès qu'il
    // apparaît (l'aperçu a rendu son rapport → `previewed` est passé à vrai).
    await userEvent.click(await within(dialog).findByRole('button', { name: /Confirmer l.import/i }))

    await waitFor(() => expect(importerCompteursUsageCsv).toHaveBeenNthCalledWith(2, {
      contenu: csv, apercu: false,
    }))
    // Vérifie explicitement l'absence de la clé (pas seulement une valeur falsy).
    expect(importerCompteursUsageCsv.mock.calls[1][0]).not.toHaveProperty('ecraser')
  })

  it('WIR251 — exporte le catalogue en .xlsx', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByText('Maintenance standard')).toBeInTheDocument())

    await userEvent.click(screen.getByRole('button', { name: /Exporter \(\.xlsx\)/i }))

    await waitFor(() => expect(exportCatalogueAbonnement).toHaveBeenCalledTimes(1))
  })
})
