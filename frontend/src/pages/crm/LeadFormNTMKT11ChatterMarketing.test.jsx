import { describe, it, expect, vi, afterEach, beforeAll } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import crmReducer from '../../features/crm/store/crmSlice'
import LeadForm from './LeadForm'

/* NTMKT11 — les touches marketing (XMKT16, `crm.services.
   noter_touche_marketing`) s'écrivent en `kind='note'` avec un texte
   `Campagne « <nom> » <verbe>` / `Séquence « <nom> » …` (aucun `kind` dédié
   ni FK campagne côté backend — contrainte connue, suivie séparément). Le
   chatter doit les distinguer visuellement (icône Megaphone dédiée) et,
   quand la campagne/séquence est résolue par nom depuis les listes
   marketing déjà exposées (NTMKT2/NTMKT6), afficher un lien cliquable vers
   `CampagneDetail`/`SequenceDetail`. */

vi.mock('react-router-dom', async (orig) => ({
  ...(await orig()),
  useNavigate: () => vi.fn(),
}))

const HISTORIQUE = [
  { id: 1, kind: 'note', body: 'Campagne « Réveil été » envoyée', user_nom: null, created_at: new Date().toISOString() },
  { id: 2, kind: 'note', body: 'Campagne « Réveil été » ouverte', user_nom: null, created_at: new Date().toISOString() },
  { id: 3, kind: 'note', body: 'Appel client — intéressé', user_nom: 'Sami', created_at: new Date().toISOString() },
]

vi.mock('../../api/axios', () => ({
  default: {
    get: (url) => (url.includes('/historique/')
      ? Promise.resolve({ data: HISTORIQUE })
      : Promise.resolve({ data: [] })),
    post: () => Promise.resolve({ data: {} }),
  },
}))

vi.mock('../../api/crmApi', () => ({
  default: {
    getAssignableUsers: () => Promise.resolve({ data: [] }),
    getTags: () => Promise.resolve({ data: [] }),
    getMotifsPerte: () => Promise.resolve({ data: [] }),
    getLeadDuplicates: () => Promise.resolve({ data: [] }),
    checkDuplicates: () => Promise.resolve({ data: [] }),
    getCanaux: () => Promise.resolve({ data: [] }),
  },
}))

const mocks = vi.hoisted(() => ({
  campagnesList: vi.fn(),
  sequencesList: vi.fn(),
}))

vi.mock('../../api/marketingApi', () => ({
  default: {
    unwrapList: (res) => {
      const data = res?.data
      return Array.isArray(data) ? data : (data?.results || [])
    },
    campagnes: { list: mocks.campagnesList },
    sequences: { list: mocks.sequencesList },
  },
}))

vi.mock('../../api/ventesApi', () => ({ default: {} }))
vi.mock('../../api/installationsApi', () => ({ default: {} }))

vi.mock('../../components/Avatar', () => ({ default: () => null }))
vi.mock('../../components/AssigneePicker', () => ({ default: () => null }))
vi.mock('../../components/ActivitiesPanel', () => ({ default: () => null }))
vi.mock('../../components/AttachmentsPanel', () => ({ default: () => null }))
vi.mock('../../components/CustomFieldsInput', () => ({ default: () => null }))
vi.mock('./leads/SigneDialog', () => ({ default: () => null }))
vi.mock('./leads/AppointmentBooker', () => ({ default: () => null }))
vi.mock('./leads/LeadDevisPanel', () => ({ default: () => null }))

function mockMatchMedia() {
  window.matchMedia = (query) => ({
    matches: false, media: query, onchange: null,
    addEventListener: () => {}, removeEventListener: () => {},
    addListener: () => {}, removeListener: () => {}, dispatchEvent: () => false,
  })
}

beforeAll(() => { if (typeof window.matchMedia !== 'function') mockMatchMedia() })
afterEach(() => { cleanup(); vi.clearAllMocks() })

function makeStore() {
  return configureStore({
    reducer: { crm: crmReducer },
    middleware: (getDefaultMiddleware) => getDefaultMiddleware({ serializableCheck: false }),
  })
}

const EDIT_LEAD = {
  id: 42, nom: 'Alaoui', prenom: 'Hassan', stage: 'NEW',
  devis: [], devis_auto: { pret: true, message: null },
  facture_hiver: 500, facture_ete: null, ete_differente: false,
  custom_data: {},
}

function renderLeadForm() {
  const store = makeStore()
  render(
    <Provider store={store}>
      <LeadForm lead={EDIT_LEAD} onClose={vi.fn()} onSaved={vi.fn()} />
    </Provider>,
  )
}

describe('LeadForm — chatter : touches marketing distinguées (NTMKT11)', () => {
  it('un lead touché par 2 campagnes montre chaque touche avec un lien cliquable', async () => {
    mocks.campagnesList.mockResolvedValue({ data: [{ id: 7, nom: 'Réveil été' }] })
    mocks.sequencesList.mockResolvedValue({ data: [] })
    renderLeadForm()

    // Les 2 notes marketing sont visibles.
    await screen.findByText(/Campagne « Réveil été » envoyée/)
    expect(screen.getByText(/Campagne « Réveil été » ouverte/)).toBeInTheDocument()

    // Distinction visuelle : icône Megaphone dédiée (classe CSS marquée).
    const marketingItems = document.querySelectorAll('.chatter-item-marketing')
    expect(marketingItems.length).toBe(2)

    // Le lien vers la campagne se résout après chargement des listes marketing.
    await waitFor(() => {
      const liens = screen.getAllByText('Voir la campagne')
      expect(liens.length).toBe(2)
      expect(liens[0].closest('a')).toHaveAttribute('href', '/marketing/campagnes/7')
    })
  })

  it('la note manuelle générique reste un rendu simple, sans lien si le nom ne correspond à aucune campagne', async () => {
    mocks.campagnesList.mockResolvedValue({ data: [] })
    mocks.sequencesList.mockResolvedValue({ data: [] })
    renderLeadForm()
    await screen.findByText(/Appel client — intéressé/)
    // Les 2 touches marketing restent taguées même sans résolution de lien
    // (nom absent des listes chargées) — jamais de lien cassé affiché.
    expect(document.querySelectorAll('.chatter-item-marketing')).toHaveLength(2)
    await waitFor(() => expect(mocks.campagnesList).toHaveBeenCalled())
    expect(screen.queryByText('Voir la campagne')).toBeNull()
  })
})
