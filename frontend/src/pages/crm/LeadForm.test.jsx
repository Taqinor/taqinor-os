import { describe, it, expect, vi, afterEach, beforeAll } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import crmReducer from '../../features/crm/store/crmSlice'
import LeadForm from './LeadForm'

/* U1 — LeadForm : en mode ÉDITION, « Mettre à jour » garde la modale ouverte,
   affiche « Enregistré » et permet d'enchaîner sur le panneau devis inline.
   À la CRÉATION, la fermeture (onClose) reste déclenchée normalement. */

// ── Mocks des API et sous-composants lourds ──────────────────────────────────

const UPDATED_LEAD = {
  id: 42, nom: 'Alaoui', prenom: 'Hassan', stage: 'CONTACTED',
  devis: [], devis_auto: { pret: true, message: null },
  facture_hiver: 800, facture_ete: null, ete_differente: false,
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
    updateLead: () => Promise.resolve({ data: UPDATED_LEAD }),
    createLead: () => Promise.resolve({ data: { id: 99, nom: 'Nouveau', devis: [] } }),
    getAssignableUsers: () => Promise.resolve({ data: [] }),
    getTags: () => Promise.resolve({ data: [] }),
    getMotifsPerte: () => Promise.resolve({ data: [] }),
    getLeadDuplicates: () => Promise.resolve({ data: [] }),
    checkDuplicates: () => Promise.resolve({ data: [] }),
    getCanaux: () => Promise.resolve({ data: [] }),
    getLead: () => Promise.resolve({ data: UPDATED_LEAD }),
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
vi.mock('./leads/LeadDevisPanel', () => ({
  default: ({ mode }) => (
    <div data-testid="lead-devis-panel" data-mode={mode}>PanneauDevis</div>
  ),
}))

function mockMatchMedia() {
  window.matchMedia = (query) => ({
    matches: false, media: query, onchange: null,
    addEventListener: () => {}, removeEventListener: () => {},
    addListener: () => {}, removeListener: () => {}, dispatchEvent: () => false,
  })
}

beforeAll(() => { if (typeof window.matchMedia !== 'function') mockMatchMedia() })
afterEach(() => { cleanup(); vi.clearAllMocks() })

// ── Helpers ───────────────────────────────────────────────────────────────────

const EDIT_LEAD = {
  id: 42, nom: 'Alaoui', prenom: 'Hassan', stage: 'NEW',
  devis: [], devis_auto: { pret: true, message: null },
  facture_hiver: 500, facture_ete: null, ete_differente: false,
  custom_data: {},
}

function makeStore() {
  return configureStore({
    reducer: { crm: crmReducer },
    middleware: (getDefaultMiddleware) => getDefaultMiddleware({ serializableCheck: false }),
  })
}

function renderLeadForm(props = {}) {
  const store = makeStore()
  // Pré-injecter updateLead comme fulfilled dans la slice via dispatch simulé.
  // On utilise la vraie slice mais on mocke crmApi.updateLead au niveau réseau.
  const onClose = props.onClose ?? vi.fn()
  const onSaved = props.onSaved ?? vi.fn()
  render(
    <Provider store={store}>
      <LeadForm onClose={onClose} onSaved={onSaved} {...props} />
    </Provider>,
  )
  return { onClose, onSaved }
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe('LeadForm U1 — mise à jour garde la modale ouverte', () => {
  it('affiche le bouton « Mettre à jour » en mode édition', () => {
    renderLeadForm({ lead: EDIT_LEAD })
    expect(screen.getByRole('button', { name: 'Mettre à jour' })).toBeInTheDocument()
  })

  it('après « Mettre à jour » : onClose N\'est PAS appelé + « Enregistré » visible', async () => {
    const onClose = vi.fn()
    const onSaved = vi.fn()
    renderLeadForm({ lead: EDIT_LEAD, onClose, onSaved })

    fireEvent.click(screen.getByRole('button', { name: 'Mettre à jour' }))

    // « Enregistré » doit apparaître (sans fermer).
    await waitFor(() =>
      expect(screen.getByText('✓ Enregistré')).toBeInTheDocument(),
    )
    // La modale N'EST PAS fermée.
    expect(onClose).not.toHaveBeenCalled()
    // La liste parente est bien rafraîchie.
    expect(onSaved).toHaveBeenCalled()
  })

  it('update → panneau devis s\'ouvre en inline après sauvegarde sans rouvrir la fiche', async () => {
    const onClose = vi.fn()
    renderLeadForm({ lead: EDIT_LEAD, onClose })

    // Sauvegarder d'abord.
    fireEvent.click(screen.getByRole('button', { name: 'Mettre à jour' }))
    await waitFor(() => expect(screen.getByText('✓ Enregistré')).toBeInTheDocument())
    expect(onClose).not.toHaveBeenCalled()

    // Ouvrir le panneau devis automatique (toujours disponible car devisReady=true).
    fireEvent.click(screen.getByRole('button', { name: /Devis automatique/i }))
    await waitFor(() =>
      expect(screen.getByTestId('lead-devis-panel')).toBeInTheDocument(),
    )
    expect(onClose).not.toHaveBeenCalled()
  })

  it('à la CRÉATION, onClose est appelé après création réussie', async () => {
    const onClose = vi.fn()
    renderLeadForm({ lead: null, onClose })

    // Renseigner le nom (requis). Le label « Nom » n'est pas associé à son
    // input (label frère, sans htmlFor) → on cible l'input via son groupe.
    const nomLabel = screen.getByText(/^Nom/, { selector: 'label' })
    const nomInput = nomLabel.parentElement.querySelector('input')
    fireEvent.change(nomInput, { target: { value: 'Ben Youssef' } })

    fireEvent.click(screen.getByRole('button', { name: 'Créer le lead' }))

    await waitFor(() => expect(onClose).toHaveBeenCalled())
  })
})
