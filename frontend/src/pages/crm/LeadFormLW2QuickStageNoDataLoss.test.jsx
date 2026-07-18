import { describe, it, expect, vi, afterEach, beforeAll } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import crmReducer from '../../features/crm/store/crmSlice'
import LeadForm from './LeadForm'

/* LW2 — Perte de données #1 : le raccourci d'étape 1-4 (quickChangeStage)
   PATCHe seulement {stage} côté serveur mais blanchissait TOUT l'instantané
   « propre » (isDirty → faux) même si un AUTRE champ avait une édition non
   sauvée en cours — fermeture/J-K silencieuse, éditions perdues. Ce test
   couvre le DoD exact : taper dans Nom, presser « 2 », vérifier que isDirty
   reste vrai (via la garde « Annuler ») et que la valeur tapée est intacte. */

const EDIT_LEAD = {
  id: 42, nom: 'Alaoui', prenom: 'Hassan', stage: 'NEW',
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
    // Le raccourci « 2 » PATCHe {stage: 'CONTACTED'} — on renvoie le lead
    // avec cette seule clé mise à jour, comme le ferait le serveur réel.
    updateLead: (id, data) => Promise.resolve({ data: { ...EDIT_LEAD, ...data } }),
    createLead: () => Promise.resolve({ data: { id: 99, nom: 'Nouveau', devis: [] } }),
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

function renderLeadForm(props = {}) {
  const store = makeStore()
  const onClose = props.onClose ?? vi.fn()
  const onSaved = props.onSaved ?? vi.fn()
  render(
    <Provider store={store}>
      <LeadForm lead={EDIT_LEAD} onClose={onClose} onSaved={onSaved} {...props} />
    </Provider>,
  )
  return { onClose, onSaved }
}

describe('LeadForm LW2 — quickChangeStage (1-4) ne blanchit pas les éditions en cours', () => {
  it('taper dans Nom puis presser « 2 » : la valeur tapée reste intacte et isDirty reste vrai', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)
    const onSaved = vi.fn()
    renderLeadForm({ onSaved })

    const nomInput = document.getElementById('lf-nom')
    fireEvent.change(nomInput, { target: { value: 'Bennani' } })
    expect(nomInput.value).toBe('Bennani')

    // Raccourci « 2 » = 2ᵉ étape du pipeline (CONTACTED) — touche hors saisie,
    // câblée par useFocusedRecordShortcuts sur `window` (bubble via document).
    fireEvent.keyDown(document, { key: '2' })

    // Laisse le PATCH {stage} (async) se résoudre — `onSaved` n'est appelé
    // qu'APRÈS la mise à jour de fields/cleanFieldsJSON dans quickChangeStage.
    await waitFor(() => expect(onSaved).toHaveBeenCalled())
    expect(nomInput.value).toBe('Bennani')

    // Preuve indirecte que isDirty est resté vrai : « Annuler » redemande
    // confirmation (confirmLeaveIfDirty) au lieu de fermer directement — si
    // quickChangeStage avait blanchi l'instantané propre, isDirty serait
    // faux et aucune confirmation ne serait demandée.
    fireEvent.click(screen.getByRole('button', { name: 'Annuler' }))
    expect(confirmSpy).toHaveBeenCalled()
  })

  it('sans autre édition en cours, le raccourci de stage redevient propre (isDirty faux, pas de confirmation)', async () => {
    const onClose = vi.fn()
    const onSaved = vi.fn()
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)
    renderLeadForm({ onClose, onSaved })

    fireEvent.keyDown(document, { key: '2' })
    await waitFor(() => expect(onSaved).toHaveBeenCalled())

    // Rien d'autre n'a été touché : le raccourci commit stage ET son propre
    // instantané — « Annuler » doit fermer directement, sans confirmation.
    fireEvent.click(screen.getByRole('button', { name: 'Annuler' }))
    expect(confirmSpy).not.toHaveBeenCalled()
    expect(onClose).toHaveBeenCalled()
  })
})
