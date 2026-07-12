import { describe, it, expect, vi, afterEach, beforeAll } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import crmReducer from '../../features/crm/store/crmSlice'
import ClientForm from './ClientForm'

/* J139 — ClientForm rendu dans une ResponsiveDialog (modale ≥768 px / tiroir bas
   <768 px). On vérifie que le formulaire s'ouvre dans un [role="dialog"] avec le
   bon titre et le bon bouton de soumission, aux deux points de rupture. */

// VX170 — ClientForm compose désormais useFormSafety → useNavigationGuard →
// useConfirmDialog() ; le mock doit exposer ce hook (sinon la garde plante au
// montage). Repli neutre : aucune confirmation réelle n'est déclenchée ici.
vi.mock('../../ui/confirm', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
  useConfirmDialog: () => ({ confirm: vi.fn(), confirmDelete: vi.fn() }),
}))
vi.mock('../../components/AttachmentsPanel', () => ({ default: () => null }))

function mockMatchMedia(mobile) {
  window.matchMedia = (query) => ({
    matches: mobile, media: query, onchange: null,
    addEventListener: () => {}, removeEventListener: () => {},
    addListener: () => {}, removeListener: () => {}, dispatchEvent: () => false,
  })
}

beforeAll(() => { if (typeof window.matchMedia !== 'function') mockMatchMedia(false) })
afterEach(() => { cleanup(); vi.clearAllMocks() })

const renderForm = (props = {}) => {
  const store = configureStore({ reducer: { crm: crmReducer } })
  return render(
    <Provider store={store}>
      <ClientForm onClose={vi.fn()} {...props} />
    </Provider>,
  )
}

describe('ClientForm (J139 — ResponsiveDialog)', () => {
  it('ouvre la modale « Nouveau client » sur bureau', () => {
    mockMatchMedia(false)
    renderForm()
    expect(document.querySelector('[role="dialog"]')).toBeInTheDocument()
    expect(screen.getByText('Nouveau client')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Créer le client' })).toBeInTheDocument()
  })

  it('rend le tiroir bas (Sheet) sous 768 px', () => {
    mockMatchMedia(true)
    renderForm()
    expect(document.querySelector('[role="dialog"]')).toBeInTheDocument()
    expect(screen.getByText('Nouveau client')).toBeInTheDocument()
  })

  it('affiche « Mettre à jour » en édition', () => {
    mockMatchMedia(false)
    renderForm({ client: { id: 9, nom: 'Dupont', type_client: 'particulier' } })
    expect(screen.getByText('Éditer le client')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Mettre à jour' })).toBeInTheDocument()
  })
})
