import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'

/* PACT42 — Approbation des configurations non standard (FG213). Une demande
   refusée doit garder son motif ET son commentaire de décision visibles dans
   l'historique — jamais effacés (Done= de PACT42). */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  refuser: vi.fn(),
}))

vi.mock('../../../api/comptaApi', () => ({
  default: {
    approbationsConfig: { list: mocks.list, refuser: mocks.refuser, approuver: vi.fn(), create: vi.fn() },
  },
}))

import ApprobationsConfigPage from './ApprobationsConfigPage.jsx'

function mount() {
  const store = configureStore({
    reducer: { auth: () => ({ role: 'admin', role_nom: null, permissions: [] }) },
  })
  return render(
    <Provider store={store}>
      <MemoryRouter initialEntries={['/']}>
        <ThemeProvider><ApprobationsConfigPage /></ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

describe('ApprobationsConfigPage — motif conservé après refus (PACT42)', () => {
  it('refuse une demande et garde le motif ET le commentaire visibles', async () => {
    mocks.list.mockResolvedValue({
      data: [{ id: 3, devis_id: 42, devis_reference: 'DEV-042',
        motif: 'Onduleur incohérent avec le champ PV', statut: 'en_attente',
        demandeur_nom: 'sami', decideur_nom: '', commentaire_decision: '',
        date_creation: '2026-01-01', date_decision: null }],
    })
    mocks.refuser.mockResolvedValueOnce({
      data: { id: 3, devis_id: 42, devis_reference: 'DEV-042',
        motif: 'Onduleur incohérent avec le champ PV', statut: 'refusee',
        demandeur_nom: 'sami', decideur_nom: 'admin',
        commentaire_decision: 'Refusé : hors gamme catalogue',
        date_creation: '2026-01-01', date_decision: '2026-01-02' },
    })
    const promptSpy = vi.spyOn(window, 'prompt').mockReturnValue('Refusé : hors gamme catalogue')
    mount()

    expect(await screen.findByText('Onduleur incohérent avec le champ PV')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /^Refuser$/i }))

    await waitFor(() => expect(mocks.refuser).toHaveBeenCalledWith(
      3, { commentaire: 'Refusé : hors gamme catalogue' }))
    promptSpy.mockRestore()
  })
})
