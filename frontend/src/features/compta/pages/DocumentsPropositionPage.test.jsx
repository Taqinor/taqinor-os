import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'

/* PACT40 — Bibliothèque d'annexes de proposition (FG215). Purement additif :
   ne touche ni le générateur de devis ni le moteur PDF (règle #4 du dépôt) —
   cet écran gère uniquement la BIBLIOTHÈQUE, jamais le rendu. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

const mocks = vi.hoisted(() => ({ list: vi.fn() }))

vi.mock('../../../api/comptaApi', () => ({
  default: { documentsProposition: { list: mocks.list, update: vi.fn() } },
}))

import DocumentsPropositionPage from './DocumentsPropositionPage.jsx'

function mount() {
  const store = configureStore({
    reducer: { auth: () => ({ role: 'admin', role_nom: null, permissions: [] }) },
  })
  return render(
    <Provider store={store}>
      <MemoryRouter initialEntries={['/']}>
        <ThemeProvider><DocumentsPropositionPage /></ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

describe('DocumentsPropositionPage — bibliothèque (PACT40)', () => {
  it('liste les annexes réelles renvoyées par le serveur', async () => {
    mocks.list.mockResolvedValue({
      data: [{ id: 1, titre: 'Garanties matériel', type_document: 'garanties',
        type_document_display: 'Garanties', contenu: '10 ans onduleur, 25 ans panneaux',
        fichier: null, ordre: 1, actif: true, date_creation: '2026-01-01' }],
    })
    mount()

    expect(await screen.findByText('Garanties matériel')).toBeInTheDocument()
    expect(screen.getByText('Garanties')).toBeInTheDocument()
  })
})
