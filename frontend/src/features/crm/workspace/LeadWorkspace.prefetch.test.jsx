import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { LEAD_A, mockMatchMedia } from '../../../test/leadWorkspaceMocks'
import { render, screen, cleanup, act, fireEvent, waitFor } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'
import crmReducer from '../store/crmSlice'
import crmApi from '../../../api/crmApi'
import api from '../../../api/axios'
import { resetPrefetchCache, getPrefetched } from './leadPrefetch'
import LeadWorkspace from './LeadWorkspace'

/* LW24 — pré-chargement en idle des voisins de file (J/K instantané). Mêmes
   neutralisations que LeadWorkspaceCreate.test.jsx. Le RE-FETCH en
   arrière-plan après un rendu-cache (garde res.id===leadId) est le même
   mécanisme que le GET systématique d'ouverture de LW25 — vérifié dans
   LeadWorkspace.skeleton.test.jsx une fois ce mécanisme construit ; ici on
   couvre la partie propre à CETTE tâche : alimentation du cache + premier
   rendu instantané depuis le cache. */
vi.mock('../../../pages/crm/leads/LeadDevisPanel', () => ({ default: () => null }))
vi.mock('../../../pages/crm/leads/SigneDialog', () => ({ default: () => null }))

vi.mock('../../../api/crmApi', async () => (await import('../../../test/leadWorkspaceMocks')).crmApiLeadWorkspace({
  // R5A-N5b / R5A-N6 — les sections et rails RÉELS (derniers tests du fichier) lisent aussi ces deux routes.
  getLeadPhotoToit: vi.fn(() => Promise.resolve({ data: { visite_id: null, url: null, texture_calage: null } })),
  villeStatut: vi.fn(() => Promise.resolve({ data: { statut: 'connue' } })),
}))
vi.mock('../../../hooks/useDuplicateCheck', () => ({ useDuplicateCheck: () => [] }))
// R5A-N6 — le serveur répond 404 « conception_absente » : réponse normale, comptée ici.
const { conception404 } = vi.hoisted(() => ({
  conception404: vi.fn(() => Promise.reject(Object.assign(new Error('404'), { response: { status: 404 } }))),
}))
vi.mock('../../../api/ventesApi', () => ({
  default: new Proxy({}, {
    get: (cible, cle) => (cle === 'getConceptionLead' ? conception404 : vi.fn(() => Promise.resolve({ data: [] }))),
  }),
}))

const LEAD_B_ROW = { id: 2, nom: 'Karim', stage: 'NEW' } // ligne PARTIELLE de liste

beforeEach(() => {
  mockMatchMedia(false)
  try { localStorage.clear() } catch { /* noop */ }
  try { sessionStorage.clear() } catch { /* noop */ }
  resetPrefetchCache()
})
afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  try { sessionStorage.clear() } catch { /* noop */ }
  crmApi.getLead.mockImplementation(() => Promise.resolve({ data: {} }))
})

function makeStore() {
  return configureStore({ reducer: { crm: crmReducer, auth: (s = { user: { id: 42 } }) => s } })
}
function tree(store, { lead, leadsQueue, onNavigateLead, onClose, onSaved }) {
  return (
    <Provider store={store}>
      <MemoryRouter>
        <LeadWorkspace
          lead={lead} leadsQueue={leadsQueue} onNavigateLead={onNavigateLead} onClose={onClose} onSaved={onSaved}
        />
      </MemoryRouter>
    </Provider>
  )
}
function renderEdit({ lead = LEAD_A, leadsQueue = null, onNavigateLead = vi.fn(), onClose = vi.fn(), onSaved = vi.fn() } = {}) {
  const store = makeStore()
  const props = { lead, leadsQueue, onNavigateLead, onClose, onSaved }
  const utils = render(tree(store, props))
  const rerenderWith = (nextProps) => utils.rerender(tree(store, { ...props, ...nextProps }))
  return { ...utils, rerenderWith }
}

describe('LW24 — pré-chargement en idle des voisins de file', () => {
  it('après ouverture de A avec file [A,B], getLead(B) est appelé en idle et peuple le cache', async () => {
    vi.useFakeTimers()
    try {
      renderEdit({ lead: LEAD_A, leadsQueue: [LEAD_A, LEAD_B_ROW] })
      await act(async () => { await vi.advanceTimersByTimeAsync(300) })
      // `advanceTimersByTimeAsync` flushe déjà les micro-tâches à chaque pas
      // — pas besoin de `waitFor` (dont le polling utiliserait les MÊMES
      // horloges factices, sans jamais avancer tout seul → faux timeout).
      expect(crmApi.getLead).toHaveBeenCalledWith(2)
      expect(getPrefetched(2)).not.toBeNull()
    } finally {
      vi.useRealTimers()
    }
  })

  it('pas de file (leadsQueue=null) : aucun pré-chargement de voisin', async () => {
    vi.useFakeTimers()
    try {
      renderEdit({ lead: LEAD_A, leadsQueue: null })
      await act(async () => { await vi.advanceTimersByTimeAsync(500) })
      const calledIds = crmApi.getLead.mock.calls.map((c) => c[0])
      expect(calledIds).not.toContain(2)
    } finally {
      vi.useRealTimers()
    }
  })

  it('naviguer vers un voisin déjà pré-chargé rend INSTANTANÉMENT la donnée complète du cache', async () => {
    vi.useFakeTimers()
    try {
      const fullB = { id: 2, nom: 'Karim', prenom: 'Fadel', stage: 'CONTACTED', ville: 'Rabat' }
      crmApi.getLead.mockImplementation((id) => (id === 2
        ? Promise.resolve({ data: fullB })
        : new Promise(() => {}))) // jamais résolu pour les autres ids — non pertinent ici

      const { rerenderWith } = renderEdit({ lead: LEAD_A, leadsQueue: [LEAD_A, LEAD_B_ROW] })
      // Idle → pré-chargement de B, résolu avec la donnée COMPLÈTE.
      await act(async () => { await vi.advanceTimersByTimeAsync(300) })
      expect(getPrefetched(2)).toEqual(fullB)

      // Navigation vers B (ligne PARTIELLE, sans prénom) — le rendu doit
      // afficher IMMÉDIATEMENT le prénom du CACHE.
      await act(async () => { rerenderWith({ lead: LEAD_B_ROW }) })
      expect(screen.getAllByText(/Karim Fadel/).length).toBeGreaterThan(0)
    } finally {
      vi.useRealTimers()
    }
  })
})

/* R5A-N5b / R5A-N6 — ouvrir une fiche SANS rien taper (rails et sections RÉELS) : jamais « sale », aucune écriture, une seule
   lecture de la conception. */
// Un lead tel que le sérialiseur le sert : décimaux en CHAÎNES, dates ISO, nulls, '' , 0, booléens, listes.
const LEAD_SERVI = {
  id: 1, nom: 'Ali', prenom: 'Ben', societe: '', email: 'ali@example.ma', telephone: '0612345678', whatsapp: null,
  adresse: '', ville: 'Casablanca', ville_reference: null, gps_lat: '33.573110', gps_lng: '-7.589843',
  stage: 'NEW', is_archived: false, owner: 3, owner_nom: 'Sami', priorite: 'normale', canal: 'meta_ads',
  facture_hiver: '800.00', facture_ete: '1200.50', ete_differente: true, surface_toit: '0', roof_age: 0,
  montant_estime: null, relance_date: '2026-11-30', date_cloture_prevue: null, tags: 'chaud, villa',
  type_installation: '', raccordement: null, note: '', custom_data: {}, jours_ouverture: [1, 2, 3], heure_debut: 8,
  compteur_puissance_kva: '12.00', chatter_recent: [], devis: [], date_modification: '2026-11-26T09:00:00Z',
}

const quitterBloque = () => {
  const ev = new Event('beforeunload', { cancelable: true })
  window.dispatchEvent(ev)
  return ev.defaultPrevented
}

function ouvrir() {
  return render(
    <Provider store={configureStore({ reducer: { crm: crmReducer, auth: (s = { user: { id: 42 }, role: 'admin' }) => s } })}>
      <MemoryRouter>
        <LeadWorkspace lead={{ ...LEAD_SERVI }} onClose={vi.fn()} onSaved={vi.fn()} />
      </MemoryRouter>
    </Provider>,
  )
}

describe('R5A-N5b — une fiche ouverte sans rien taper n’est jamais « sale »', () => {
  beforeEach(() => {
    crmApi.getLead.mockImplementation(() => Promise.resolve({ data: { ...LEAD_SERVI } }))
    crmApi.updateLead.mockImplementation(() => Promise.resolve({ data: { ...LEAD_SERVI } }))
  })

  it('lead servi avec décimaux, dates, null, 0 : aucune écriture, aucune garde, aucun brouillon en mémoire', async () => {
    ouvrir()
    await waitFor(() => expect(crmApi.getLead).toHaveBeenCalled())
    await screen.findByDisplayValue('chaud, villa')
    await new Promise((r) => { setTimeout(r, 2200) }) // au-delà du debounce d'autosauvegarde (1,5 s)
    expect(crmApi.updateLead).not.toHaveBeenCalled()
    expect(quitterBloque()).toBe(false)
    expect(sessionStorage.getItem('taqinor.lead.draft.1')).toBeNull()
  }, 15000)

  it('R5A-N6 — la conception du lead est demandée UNE fois par fiche ouverte (carte + avis brouillons), 404 sans toast ni relecture', async () => {
    ouvrir()
    await screen.findByDisplayValue('chaud, villa')
    await new Promise((r) => { setTimeout(r, 4600) }) // au-delà de l'ancien rythme de relecture (4 s)
    expect(conception404).toHaveBeenCalledTimes(1)
    expect(conception404).toHaveBeenCalledWith(1)
  }, 15000)

  it('lead neuf sans conception (200 « aucune » du contrat) : UNE requête, aucune erreur console, carte calme', async () => {
    const { exempleContrat } = await import('../../../test/fixtures/contractSamples')
    conception404.mockImplementationOnce(() => Promise.resolve({ data: exempleContrat('ventes', 'conception_lead', 'exemple_aucune') }))
    const erreurs = vi.spyOn(console, 'error').mockImplementation(() => {})
    ouvrir()
    await screen.findByDisplayValue('chaud, villa')
    await screen.findByTestId('carte-conception-sans-conception')
    await new Promise((r) => { setTimeout(r, 4600) })
    expect(conception404).toHaveBeenCalledTimes(1)
    expect(erreurs).not.toHaveBeenCalled()
    erreurs.mockRestore()
  }, 15000)

  it('une vraie saisie arme la garde, puis part en PATCH partiel', async () => {
    ouvrir()
    await screen.findByDisplayValue('chaud, villa')
    fireEvent.change(document.querySelector('#lf-tags'), { target: { value: 'chaud' } })
    await waitFor(() => expect(quitterBloque()).toBe(true))
    await waitFor(() => expect(crmApi.updateLead).toHaveBeenCalledWith(1, { tags: 'chaud' }), { timeout: 4000 })
  }, 15000)

  it('un brouillon de session qui ne diffère pas du lead servi ne rend pas la fiche « sale »', async () => {
    sessionStorage.setItem('taqinor.lead.draft.1', JSON.stringify({
      draft: { facture_hiver: '800', tags: 'chaud, villa', surface_toit: 0 }, note: '',
    }))
    ouvrir()
    await screen.findByDisplayValue('chaud, villa')
    await new Promise((r) => { setTimeout(r, 2200) })
    expect(quitterBloque()).toBe(false)
    expect(crmApi.updateLead).not.toHaveBeenCalled()
  }, 15000)

  it('un brouillon restauré qui DIFFÈRE reste protégé (garde armée) mais ne part pas tout seul ; il part au premier geste', async () => {
    sessionStorage.setItem('taqinor.lead.draft.1', JSON.stringify({ draft: { tags: 'froid' }, note: '' }))
    ouvrir()
    await screen.findByDisplayValue('froid')
    await new Promise((r) => { setTimeout(r, 2200) })
    expect(crmApi.updateLead).not.toHaveBeenCalled()
    expect(quitterBloque()).toBe(true) // du vrai travail non envoyé : la sortie reste gardée
    fireEvent.change(document.querySelector('#lf-tags'), { target: { value: 'froid, villa' } })
    await waitFor(() => expect(crmApi.updateLead).toHaveBeenCalledWith(1, { tags: 'froid, villa' }), { timeout: 4000 })
  }, 15000)

  it('R5A-N6 — l’historique de la fiche change (ligne « Conception recalculée ») : la conception est relue UNE fois', async () => {
    api.get.mockImplementation((u) => Promise.resolve({ data: u === '/crm/leads/1/historique/' ? [] : [] }))
    ouvrir()
    await screen.findByDisplayValue('chaud, villa')
    await waitFor(() => expect(api.get).toHaveBeenCalledWith('/crm/leads/1/historique/'))
    await new Promise((r) => { setTimeout(r, 50) })
    expect(conception404).toHaveBeenCalledTimes(1)
    api.get.mockImplementation((u) => Promise.resolve({ data: u === '/crm/leads/1/historique/'
      ? [{ id: 5, kind: 'note', body: 'Conception recalculée : taille changée', created_at: '2026-11-26T10:00:00Z' }] : [] }))
    act(() => { window.dispatchEvent(new Event('focus')) })
    await waitFor(() => expect(conception404).toHaveBeenCalledTimes(2))
    await new Promise((r) => { setTimeout(r, 100) })
    expect(conception404).toHaveBeenCalledTimes(2) // une relecture simple : un 404 reste calme, pas de file
  }, 15000)
})
