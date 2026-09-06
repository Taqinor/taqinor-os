import { describe, it, expect, vi, afterEach, beforeAll } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import crmReducer from '../../features/crm/store/crmSlice'
import ClientForm from './ClientForm'

/* AUDV22 (DRAFT165-123/124, ARC20) — recherche EXACTE anti-doublon (ICE/
   email) AVANT la création d'un Client, en COMPLÉMENT de la recherche floue
   QC1 existante. Un premier submit qui trouve un tiers déjà porteur de cet
   email affiche un avertissement et REFUSE de créer ; le second submit (même
   valeurs) passe — jamais bloquant côté serveur. */

vi.mock('../../ui/confirm', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
  useConfirmDialog: () => ({ confirm: vi.fn(), confirmDelete: vi.fn() }),
}))
vi.mock('../../components/AttachmentsPanel', () => ({ default: () => null }))
vi.mock('../../api/ventesApi', () => ({
  default: { getListesPrix: vi.fn(() => Promise.resolve({ data: [] })) },
}))
vi.mock('../../api/crmApi', () => ({
  default: {
    createClient: vi.fn(() => Promise.resolve({ data: { id: 1, nom: 'Nouveau Client' } })),
    searchClients: vi.fn(() => Promise.resolve({ data: [] })),
    // VX239 — useDuplicateCheck (téléphone/email vs leads) tourne en
    // permanence sur ce formulaire, sans rapport avec AUDV22 : mocké pour ne
    // pas polluer les tests d'un rejet non lié.
    checkDuplicates: vi.fn(() => Promise.resolve({ data: [] })),
  },
}))
vi.mock('../../api/tiersApi', () => ({
  default: { verifierDoublon: vi.fn() },
}))

import crmApi from '../../api/crmApi'
import tiersApi from '../../api/tiersApi'

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

describe('ClientForm — anti-doublon exact ICE/email (AUDV22)', () => {
  it('un email déjà porté par un tiers affiche un avertissement et refuse le premier submit', async () => {
    const user = userEvent.setup()
    tiersApi.verifierDoublon.mockResolvedValue({
      data: {
        ice_matches: [],
        email_matches: [{ id: 5, nom: 'Client Existant', roles: { client: true } }],
      },
    })
    renderForm()

    await user.type(screen.getByRole('textbox', { name: 'Nom' }), 'Nouveau Client')
    await user.type(screen.getByLabelText('Email — optionnel'), 'existant@example.ma')
    await user.click(screen.getByRole('button', { name: 'Créer le client' }))

    await waitFor(() => expect(tiersApi.verifierDoublon).toHaveBeenCalledWith(
      expect.objectContaining({ email: 'existant@example.ma' })))
    expect(await screen.findByTestId('cf-dup-warning')).toHaveTextContent('Client Existant')
    expect(crmApi.createClient).not.toHaveBeenCalled()
  })

  it('le second submit (même valeurs) crée malgré le doublon signalé', async () => {
    const user = userEvent.setup()
    tiersApi.verifierDoublon.mockResolvedValue({
      data: {
        ice_matches: [],
        email_matches: [{ id: 5, nom: 'Client Existant', roles: { client: true } }],
      },
    })
    renderForm()

    await user.type(screen.getByRole('textbox', { name: 'Nom' }), 'Nouveau Client')
    await user.type(screen.getByLabelText('Email — optionnel'), 'existant@example.ma')
    await user.click(screen.getByRole('button', { name: 'Créer le client' }))
    await screen.findByTestId('cf-dup-warning')

    await user.click(screen.getByRole('button', { name: 'Créer le client' }))
    await waitFor(() => expect(crmApi.createClient).toHaveBeenCalledTimes(1))
    // Un seul appel de vérification : le second submit ne revérifie pas.
    expect(tiersApi.verifierDoublon).toHaveBeenCalledTimes(1)
  })

  it('sans aucun doublon, le premier submit crée directement', async () => {
    const user = userEvent.setup()
    tiersApi.verifierDoublon.mockResolvedValue({
      data: { ice_matches: [], email_matches: [] },
    })
    renderForm()

    await user.type(screen.getByRole('textbox', { name: 'Nom' }), 'Client Propre')
    await user.type(screen.getByLabelText('Email — optionnel'), 'propre@example.ma')
    await user.click(screen.getByRole('button', { name: 'Créer le client' }))

    await waitFor(() => expect(crmApi.createClient).toHaveBeenCalledTimes(1))
    expect(screen.queryByTestId('cf-dup-warning')).not.toBeInTheDocument()
  })

  it('sans ICE ni email, aucune vérification n\'est déclenchée', async () => {
    const user = userEvent.setup()
    renderForm()

    await user.type(screen.getByRole('textbox', { name: 'Nom' }), 'Client Minimal')
    await user.click(screen.getByRole('button', { name: 'Créer le client' }))

    await waitFor(() => expect(crmApi.createClient).toHaveBeenCalledTimes(1))
    expect(tiersApi.verifierDoublon).not.toHaveBeenCalled()
  })
})
