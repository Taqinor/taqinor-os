import { describe, it, expect, vi, afterEach, beforeAll } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import crmReducer from '../../features/crm/store/crmSlice'
import LeadForm from './LeadForm'

/* LW4 — DoD : (1) champ modifié + « a »/bouton Archiver → window.confirm est
   appelé et l'archivage n'a pas lieu tant que l'utilisateur ne confirme pas ;
   (2) création en rafale (« Créer un autre ») → customData est vide pour le
   2ᵉ lead (plus d'héritage silencieux des champs personnalisés du 1er). */

const EDIT_LEAD = {
  id: 42, nom: 'Alaoui', prenom: 'Hassan', stage: 'NEW', is_archived: false,
  devis: [], devis_auto: { pret: true, message: null },
  facture_hiver: 500, facture_ete: null, ete_differente: false,
  custom_data: {},
}

vi.mock('react-router-dom', async (orig) => ({
  ...(await orig()),
  useNavigate: () => vi.fn(),
}))

vi.mock('../../api/axios', () => ({
  default: {
    get: () => Promise.resolve({ data: [] }),
    post: () => Promise.resolve({ data: {} }),
  },
}))

vi.mock('../../api/crmApi', () => ({
  default: {
    updateLead: (id, data) => Promise.resolve({ data: { ...EDIT_LEAD, ...data } }),
    createLead: () => Promise.resolve({ data: { id: 99, nom: 'Nouveau', devis: [] } }),
    archiverLead: () => Promise.resolve({ data: { ...EDIT_LEAD, is_archived: true } }),
    restaurerLead: () => Promise.resolve({ data: { ...EDIT_LEAD, is_archived: false } }),
    getAssignableUsers: () => Promise.resolve({ data: [] }),
    getTags: () => Promise.resolve({ data: [] }),
    getMotifsPerte: () => Promise.resolve({ data: [] }),
    getLeadDuplicates: () => Promise.resolve({ data: [] }),
    checkDuplicates: () => Promise.resolve({ data: [] }),
    getCanaux: () => Promise.resolve({ data: [] }),
    getLead: () => Promise.resolve({ data: EDIT_LEAD }),
  },
}))

vi.mock('../../api/ventesApi', () => ({ default: {} }))
vi.mock('../../api/installationsApi', () => ({ default: {} }))

vi.mock('../../components/Avatar', () => ({ default: () => null }))
vi.mock('../../components/AssigneePicker', () => ({ default: () => null }))
vi.mock('../../components/ActivitiesPanel', () => ({ default: () => null }))
vi.mock('../../components/AttachmentsPanel', () => ({ default: () => null }))
// LW4 — contrairement aux autres tests LeadForm (mock -> null), on a besoin
// d'un vrai contrôle pour prouver que `customData` repart à `{}` : un
// mini-composant fidèle au contrat `{ value, onChange }` de CustomFieldsInput.
vi.mock('../../components/CustomFieldsInput', () => ({
  default: ({ value, onChange }) => (
    <div>
      <span data-testid="custom-data-json">{JSON.stringify(value)}</span>
      <button type="button" onClick={() => onChange({ champA: 'valeur-test' })}>
        Renseigner champ perso
      </button>
    </div>
  ),
}))
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
afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  localStorage.removeItem('taqinor.leadForm.creerUnAutre')
})

function makeStore() {
  return configureStore({
    reducer: { crm: crmReducer },
    middleware: (getDefaultMiddleware) => getDefaultMiddleware({ serializableCheck: false }),
  })
}

function renderLeadForm(props = {}) {
  const store = makeStore()
  const onClose = props.onClose ?? vi.fn()
  const onSaved = props.onSaved ?? vi.fn()
  render(
    <Provider store={store}>
      <LeadForm onClose={onClose} onSaved={onSaved} {...props} />
    </Provider>,
  )
  return { onClose, onSaved }
}

describe('LeadForm LW4 — archivage garde-fou + reset complet en rafale', () => {
  it('champ modifié + « Archiver » → confirmation demandée, archivage annulé si refusée', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false)
    const { onClose, onSaved } = renderLeadForm({ lead: EDIT_LEAD })

    const nomInput = document.getElementById('lf-nom')
    fireEvent.change(nomInput, { target: { value: 'Bennani' } })

    fireEvent.click(screen.getByRole('button', { name: 'Archiver' }))

    expect(confirmSpy).toHaveBeenCalled()
    // Refusé → l'archivage n'a jamais eu lieu (ni fermeture ni refresh liste),
    // `toggleArchive` retourne AVANT tout `await` dans ce cas (synchrone).
    expect(onSaved).not.toHaveBeenCalled()
    expect(onClose).not.toHaveBeenCalled()
  })

  it('champ modifié + « Archiver » confirmé → archive normalement (comportement inchangé)', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    const { onClose, onSaved } = renderLeadForm({ lead: EDIT_LEAD })

    fireEvent.change(document.getElementById('lf-nom'), { target: { value: 'Bennani' } })
    fireEvent.click(screen.getByRole('button', { name: 'Archiver' }))

    await waitFor(() => expect(onSaved).toHaveBeenCalled())
    expect(onClose).toHaveBeenCalled()
  })

  it('« Créer un autre » : customData ne survit pas au reset (2ᵉ lead de la rafale part vide)', async () => {
    localStorage.setItem('taqinor.leadForm.creerUnAutre', '1')
    renderLeadForm({ lead: null })

    // Nom requis pour passer la validation.
    fireEvent.change(document.getElementById('lf-nom'), { target: { value: 'Ben Youssef' } })
    // Renseigner un champ personnalisé sur CE lead (avant sa création).
    fireEvent.click(screen.getByRole('button', { name: 'Renseigner champ perso' }))
    expect(screen.getByTestId('custom-data-json').textContent).toBe('{"champA":"valeur-test"}')

    fireEvent.click(screen.getByRole('button', { name: 'Créer le lead' }))

    // « Créer un autre » reset le formulaire au lieu de fermer — customData
    // doit repartir à `{}`, jamais hériter du lead précédent.
    await waitFor(() =>
      expect(screen.getByTestId('custom-data-json').textContent).toBe('{}'),
    )
  })
})
