// R5A-N5b — ouvrir une fiche lead SANS rien taper : aucune saisie « sale », aucune garde du navigateur, aucune écriture.
// Nouveau fichier car : les rails et sections RÉELS (aucun mock de ContextRail/IdentityRail/AssigneePicker/CustomFieldsInput)
// sont montés ici ; les suites LeadWorkspace.* existantes les remplacent par des sondes au niveau du module.
//
// Run : npx vitest run src/features/crm/workspace/LeadWorkspace.sansGeste.test.jsx
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { makeStore } from '../../../test/leadWorkspaceHarness'
import { mockMatchMedia } from '../../../test/leadWorkspaceMocks'
import crmApi from '../../../api/crmApi'
import LeadWorkspace from './LeadWorkspace'

vi.mock('../../../pages/crm/leads/LeadDevisPanel', () => ({ default: () => null }))
vi.mock('../../../pages/crm/leads/SigneDialog', () => ({ default: () => null }))
vi.mock('../../../hooks/useDuplicateCheck', () => ({ useDuplicateCheck: () => [] }))
vi.mock('../../../api/axios', () => ({ default: { get: vi.fn(() => Promise.resolve({ data: [] })), post: vi.fn(() => Promise.resolve({ data: {} })) } }))
vi.mock('../../../api/ventesApi', () => ({
  default: new Proxy({}, {
    get: (cible, cle) => (cle === 'getConceptionLead'
      ? vi.fn(() => Promise.reject(Object.assign(new Error('404'), { response: { status: 404 } })))
      : vi.fn(() => Promise.resolve({ data: [] }))),
  }),
}))
// Toute méthode non nommée répond une lecture vide : le test ne décrit que ce qui compte (le lead servi).
vi.mock('../../../api/crmApi', () => {
  const nommees = {}
  return {
    default: new Proxy(nommees, {
      get: (cible, cle) => {
        if (typeof cle !== 'string') return undefined
        if (!(cle in cible)) cible[cle] = vi.fn(() => Promise.resolve({ data: [] }))
        return cible[cle]
      },
      set: (cible, cle, valeur) => { cible[cle] = valeur; return true },
    }),
  }
})

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

beforeEach(() => {
  mockMatchMedia(false)
  try { localStorage.clear(); sessionStorage.clear() } catch { /* noop */ }
  crmApi.getLead = vi.fn(() => Promise.resolve({ data: { ...LEAD_SERVI } }))
  crmApi.updateLead = vi.fn(() => Promise.resolve({ data: { ...LEAD_SERVI } }))
})
afterEach(() => { cleanup() })

function ouvrir() {
  return render(
    <Provider store={makeStore(42, { role: 'admin' })}>
      <MemoryRouter>
        <LeadWorkspace lead={{ ...LEAD_SERVI }} onClose={vi.fn()} onSaved={vi.fn()} />
      </MemoryRouter>
    </Provider>,
  )
}

describe('R5A-N5b — une fiche ouverte sans rien taper n’est jamais « sale »', () => {
  it('lead servi avec décimaux, dates, null, 0 : aucune écriture, aucune garde, aucun brouillon en mémoire', async () => {
    ouvrir()
    await waitFor(() => expect(crmApi.getLead).toHaveBeenCalled())
    await screen.findByDisplayValue('chaud, villa')
    await new Promise((r) => { setTimeout(r, 2200) }) // au-delà du debounce d'autosauvegarde (1,5 s)
    expect(crmApi.updateLead).not.toHaveBeenCalled()
    expect(quitterBloque()).toBe(false)
    expect(sessionStorage.getItem('taqinor.lead.draft.1')).toBeNull()
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
})
