// NTUX9 — la palette ⌘K propose des actions contextuelles résolues par ÉCRAN
// (route active), au-delà de la fiche LeadWorkspace montée (LW26) : sur
// /ventes/devis?devis=<id>, « Générer le PDF du devis ouvert » télécharge SANS
// navigation (critère d'acceptation NTUX9) ; sur /crm/leads?lead=<id>,
// « Changer le stage du lead sélectionné » avance à l'étape suivante du funnel.
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, fireEvent, cleanup, act, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'

vi.mock('../lib/search/entityRoutes', () => ({
  ROUTE: {}, TYPE_LABEL: {}, TYPE_ACCENT: {},
  pathForType: () => '',
  useEntitySearch: () => ({ groups: [], loading: false, failed: false }),
}))

const getProposalPdf = vi.fn(() => Promise.resolve({ data: new Blob(['pdf']) }))
vi.mock('../api/ventesApi', () => ({ default: { getProposalPdf: (...a) => getProposalPdf(...a) } }))

const getLead = vi.fn(() => Promise.resolve({ data: { stage: 'CONTACTED' } }))
const updateLead = vi.fn(() => Promise.resolve({ data: {} }))
vi.mock('../api/crmApi', () => ({
  default: { getLead: (...a) => getLead(...a), updateLead: (...a) => updateLead(...a) },
}))

const downloadBlob = vi.fn()
vi.mock('../utils/downloadBlob', () => ({
  downloadBlob: (...a) => downloadBlob(...a),
  stampedFilename: (base, ext) => `${base}.${ext}`,
}))

const toastError = vi.fn()
const toastSuccess = vi.fn()
vi.mock('../ui/confirm', () => ({ toast: { error: (...a) => toastError(...a), success: (...a) => toastSuccess(...a) } }))

// AERR69 — le toast nommé + « Annuler » passe par lib/toast (mutateWithUndo).
const toastWithUndo = vi.fn()
vi.mock('../lib/toast', async (orig) => ({ ...(await orig()), toastWithUndo: (...a) => toastWithUndo(...a) }))

import { CommandPalette } from './CommandPalette'
import { ConfirmContext } from './confirm-context'

const store = configureStore({
  reducer: { auth: (s = { role: 'admin', permissions: [], modulesDesactives: [], user: null }) => s },
})

const confirmer = vi.fn(() => Promise.resolve(false))

function mountAt(path) {
  return render(
    <Provider store={store}>
      <ConfirmContext.Provider value={confirmer}>
        <MemoryRouter initialEntries={[path]}>
          <CommandPalette />
        </MemoryRouter>
      </ConfirmContext.Provider>
    </Provider>,
  )
}

function openPaletteEvent() {
  act(() => { window.dispatchEvent(new Event('taqinor:command-palette')) })
}

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('NTUX9 — actions contextuelles par écran', () => {
  it('/ventes/devis?devis=7 : propose « Générer le PDF » et l’exécute SANS navigation', async () => {
    mountAt('/ventes/devis?devis=7')
    openPaletteEvent()
    expect(screen.getByText('Générer le PDF du devis ouvert')).toBeInTheDocument()
    fireEvent.click(screen.getByText('Générer le PDF du devis ouvert'))
    await waitFor(() => expect(getProposalPdf).toHaveBeenCalledWith('7'))
    await waitFor(() => expect(downloadBlob).toHaveBeenCalled())
  })

  it('/ventes/devis (sans id ouvert) : aucune action « Générer le PDF »', () => {
    mountAt('/ventes/devis')
    openPaletteEvent()
    expect(screen.queryByText('Générer le PDF du devis ouvert')).toBeNull()
  })

  it('/crm/leads?lead=5 : « Changer le stage » avance à l’étape suivante (CONTACTED → QUOTE_SENT)', async () => {
    mountAt('/crm/leads?lead=5')
    openPaletteEvent()
    expect(screen.getByText('Changer le stage du lead sélectionné')).toBeInTheDocument()
    fireEvent.click(screen.getByText('Changer le stage du lead sélectionné'))
    await waitFor(() => expect(getLead).toHaveBeenCalledWith('5'))
    await waitFor(() => expect(updateLead).toHaveBeenCalledWith('5', { stage: 'QUOTE_SENT' }))
    await waitFor(() => expect(toastWithUndo).toHaveBeenCalled())
  })

  it('AERR69 — toast nommé + « Annuler » ; FOLLOW_UP ⇒ confirmation nommée avant SIGNED', async () => {
    getLead.mockResolvedValueOnce({ data: { stage: 'CONTACTED', nom: 'Karim B.' } })
    mountAt('/crm/leads?lead=5')
    openPaletteEvent()
    fireEvent.click(screen.getByText('Changer le stage du lead sélectionné'))
    await waitFor(() => expect(toastWithUndo).toHaveBeenCalled())
    const { message, onUndo } = toastWithUndo.mock.calls[0][0]
    expect(message).toBe('Karim B. → Devis envoyé')
    expect(toastSuccess).not.toHaveBeenCalled()
    await onUndo()
    expect(updateLead).toHaveBeenLastCalledWith('5', { stage: 'CONTACTED' })
    cleanup(); vi.clearAllMocks()

    getLead.mockResolvedValueOnce({ data: { stage: 'FOLLOW_UP', nom: 'Karim B.' } })
    mountAt('/crm/leads?lead=5')
    openPaletteEvent()
    fireEvent.click(screen.getByText('Changer le stage du lead sélectionné'))
    await waitFor(() => expect(confirmer).toHaveBeenCalled())
    expect(confirmer.mock.calls[0][0].title).toContain('Karim B.')
    await act(async () => {})
    expect(updateLead).not.toHaveBeenCalled()
    expect(toastWithUndo).not.toHaveBeenCalled()
  })

  it('lead déjà à la dernière étape active (SIGNED) : toast d’erreur, aucun PATCH', async () => {
    getLead.mockResolvedValueOnce({ data: { stage: 'SIGNED' } })
    mountAt('/crm/leads?lead=9')
    openPaletteEvent()
    fireEvent.click(screen.getByText('Changer le stage du lead sélectionné'))
    await waitFor(() => expect(getLead).toHaveBeenCalledWith('9'))
    await waitFor(() => expect(toastError).toHaveBeenCalled())
    expect(updateLead).not.toHaveBeenCalled()
  })

  it('route sans correspondance (/) : la section « Fiche ouverte » reste absente', () => {
    mountAt('/')
    openPaletteEvent()
    expect(screen.queryByText('Fiche ouverte')).toBeNull()
  })
})
