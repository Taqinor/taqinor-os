/* VTA15 — PARCOURS DE BOUT EN BOUT DU « COMMERCIAL TERRAIN » (RTL intégration).

   Le groupe VTA existe pour UNE personne : un commercial qui n'a pas accès au
   CRM. Ce fichier rejoue sa journée telle qu'il la vit :

     1. son accueil ne contient QUE la tuile « Visites » — aucune autre app,
        CRM compris (liste blanche ODY26 `app_visites_voir`) ;
     2. il ouvre « Ma journée » et voit SA visite ;
     3. il ouvre la visite ;
     4. « Terminer » lui est REFUSÉ tant qu'il manque des éléments — l'écran
        nomme les manquants SERVEUR ;
     5. une fois complet, « Terminer » passe et appelle l'action.

   LIMITE ASSUMÉE : le 403 serveur sur `/api/django/crm/leads/` (VTA4) n'est
   pas testable ici — RTL ne parle à aucun serveur. Ce qui EST vérifiable et
   vérifié côté front, c'est le refus d'INTERFACE : aucune app CRM dans son
   accueil, et plus aucune entrée/route « visite » du côté CRM après le move.
*/
import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest'
import { render, screen, act, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
  }
})

const { getMaJournee, getVisite, getVisites, terminerVisite } = vi.hoisted(() => ({
  getMaJournee: vi.fn(),
  getVisite: vi.fn(),
  getVisites: vi.fn(),
  terminerVisite: vi.fn(),
}))

vi.mock('../../api/visitesApi', () => ({
  default: {
    getMaJournee: (...a) => getMaJournee(...a),
    getVisite: (...a) => getVisite(...a),
    getVisites: (...a) => getVisites(...a),
    terminerVisite: (...a) => terminerVisite(...a),
    demarrerRouteVisite: vi.fn(),
    arriverVisite: vi.fn(),
    uploadVisitePhoto: vi.fn(),
    deleteVisitePhoto: vi.fn(),
    patchVisiteMesures: vi.fn(),
  },
}))

import AppLauncher from '../../components/layout/AppLauncher'
import MaJourneePage from '../../pages/visites/MaJourneePage'
import VisiteWizardPage from '../../pages/visites/VisiteWizardPage'

// Le rôle « Commercial terrain » de VTA4, tel que le serveur le sert :
// palier `normal`, permissions visites + le marqueur de liste blanche ODY26.
const TERRAIN = {
  role: 'normal',
  permissions: ['visites_voir', 'visites_creer', 'visites_modifier', 'app_visites_voir'],
  modulesDesactives: [],
  user: null,
}

const JOURNEE = {
  date: '2026-09-14',
  en_retard_count: 0,
  visites: [{
    id: 7,
    lead_nom: 'Client Démo',
    ville: 'Bouskoura',
    adresse: 'Quartier Démo',
    gps_lat: 33.4589,
    gps_lng: -7.6528,
    date_prevue: '2026-09-14',
    statut: 'en_cours',
    en_route_le: '2026-09-14T08:12:00Z',
    arrivee_le: '2026-09-14T08:41:00Z',
    complet: false,
    manquants_count: 1,
  }],
}

const slot = (code, libelle, etat) => ({
  code, libelle, guide: '', requis: true, min_photos: 1, etat, photos: [],
})

const visiteBase = {
  id: 7, lead: 118, statut: 'en_cours', date_prevue: '2026-09-14', date_realisee: null,
  notes: '', modifiable: true, raison_lecture_seule: '',
  photo_toit: { assemblage_etat: 'aucun', assemblage_erreur: '', url: null, texture_calage: null },
  checklist: [
    { categorie: 'toiture', libelle: 'Toiture', slots: [slot('toiture_vue_generale', 'Vue générale du toit', 'ok')] },
    { categorie: 'tableau', libelle: 'Tableau électrique', slots: [slot('tableau_ouvert', 'Tableau ouvert (disjoncteurs visibles)', 'manquant')] },
  ],
  mesures: {
    toiture: {}, tableau: {}, local_onduleur: {}, cheminement: {},
  },
  client_panel: {
    lead_nom: 'Client Démo', telephone: '+212600000000', whatsapp: '+212600000000',
    adresse: 'Quartier Démo, Bouskoura', ville: 'Bouskoura', gps_lat: 33.4589, gps_lng: -7.6528,
  },
  devis: [],
  en_route_le: '2026-09-14T08:12:00Z',
  arrivee_le: '2026-09-14T08:41:00Z',
}

const VISITE_INCOMPLETE = {
  ...visiteBase,
  completude: {
    complet: false,
    manquants: [{
      type: 'photo', categorie: 'tableau', code: 'tableau_ouvert',
      libelle: 'Tableau ouvert (disjoncteurs visibles)',
    }],
  },
}

const VISITE_COMPLETE = {
  ...visiteBase,
  checklist: [
    { categorie: 'toiture', libelle: 'Toiture', slots: [slot('toiture_vue_generale', 'Vue générale du toit', 'ok')] },
    { categorie: 'tableau', libelle: 'Tableau électrique', slots: [slot('tableau_ouvert', 'Tableau ouvert (disjoncteurs visibles)', 'ok')] },
  ],
  completude: { complet: true, manquants: [] },
}

const store = () => configureStore({ reducer: { auth: (s = TERRAIN) => s } })

function rendreAccueil() {
  const utils = render(
    <Provider store={store()}>
      <MemoryRouter><AppLauncher /></MemoryRouter>
    </Provider>,
  )
  act(() => { window.dispatchEvent(new Event('taqinor:app-launcher')) })
  return utils
}

function rendreApp(entree = '/visites') {
  return render(
    <Provider store={store()}>
      <MemoryRouter initialEntries={[entree]}>
        <Routes>
          <Route path="/visites" element={<MaJourneePage />} />
          <Route path="/visites/:id" element={<VisiteWizardPage />} />
        </Routes>
      </MemoryRouter>
    </Provider>,
  )
}

describe('VTA15 — parcours du Commercial terrain', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    window.localStorage.clear()
    getMaJournee.mockResolvedValue({ data: JOURNEE })
    getVisites.mockResolvedValue({ data: [] })
    getVisite.mockResolvedValue({ data: VISITE_INCOMPLETE })
  })

  it('1. son accueil ne contient QUE l’app Visites (ni CRM, ni le reste)', () => {
    rendreAccueil()
    const tuiles = screen.getAllByRole('listitem')
    const libelles = tuiles.map((t) => t.textContent.trim())
    expect(libelles).toContain('VISITES')
    expect(libelles.filter((l) => l && l !== 'VISITES')).toEqual([])
    expect(screen.queryByText('CRM')).not.toBeInTheDocument()
  })

  it('2→5. Ma journée → visite → « Terminer » refusé puis accepté', async () => {
    const user = userEvent.setup()
    rendreApp('/visites')

    // 2. sa journée
    expect(await screen.findByText('Client Démo')).toBeInTheDocument()

    // 3. il ouvre la visite
    await user.click(screen.getByRole('button', { name: /Ouvrir la visite/ }))
    await waitFor(() => expect(getVisite).toHaveBeenCalledWith('7'))

    // 4. « Terminer » REFUSÉ, et les manquants sont ceux du SERVEUR
    const bloque = await screen.findByRole('button', { name: 'Il manque des éléments' })
    expect(bloque).toBeDisabled()
    expect(screen.getAllByText('Tableau ouvert (disjoncteurs visibles)').length).toBeGreaterThan(0)
    expect(terminerVisite).not.toHaveBeenCalled()

    // 5. une fois complet côté serveur, le bouton passe et l'action part
    getVisite.mockResolvedValue({ data: VISITE_COMPLETE })
    terminerVisite.mockResolvedValue({ data: { ...VISITE_COMPLETE, statut: 'terminee' } })
    rendreApp('/visites/7')
    const ok = await screen.findByRole('button', { name: 'Terminer la visite' })
    expect(ok).toBeEnabled()
    await user.click(ok)
    await waitFor(() => expect(terminerVisite).toHaveBeenCalledWith('7'))
  })

  it('refus d’interface côté CRM : plus aucune entrée ni route « visite » n’y subsiste', async () => {
    const { default: crmConfig } = await import('../crm/module.config.jsx')
    expect(crmConfig.nav.items.filter((i) => String(i.to).includes('visite'))).toEqual([])
    expect(crmConfig.routes.filter((r) => String(r.path).includes('visite'))).toEqual([])
  })
})
