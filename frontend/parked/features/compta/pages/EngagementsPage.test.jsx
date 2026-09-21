import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'

/* PACT152 — Piste d'audit comptable (COMPTA39) : verifier_integrite_piste
   (backend/django_core/apps/compta/services.py:10197) renvoie EXACTEMENT
   {valide, nb_maillons, rupture} — jamais `intacte`/`detail`. Ces fixtures
   reprennent la forme réelle du serveur, jamais un dictionnaire inventé. */

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
  verifier: vi.fn(),
}))

vi.mock('../../../api/comptaApi', () => ({
  default: {
    pistesAudit: { list: mocks.list, verifier: mocks.verifier },
  },
}))

import EngagementsPage from './EngagementsPage.jsx'

function mount() {
  const store = configureStore({
    reducer: { auth: () => ({ role: 'admin', role_nom: null, permissions: [] }) },
  })
  return render(
    <Provider store={store}>
      <MemoryRouter initialEntries={['/?onglet=pisteAudit']}>
        <ThemeProvider><EngagementsPage /></ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

describe('PisteAuditPanel — intégrité de la piste d’audit (PACT152)', () => {
  beforeAll(() => {
    mocks.list.mockResolvedValue({ data: [] })
  })

  it('affiche « Rupture détectée » et le maillon en cause quand valide=false', async () => {
    mocks.verifier.mockResolvedValueOnce({
      data: { valide: false, nb_maillons: 42, rupture: 17 },
    })
    mount()
    const bouton = await screen.findByRole('button', { name: /Vérifier l.intégrité/ })
    fireEvent.click(bouton)

    await waitFor(() => expect(mocks.verifier).toHaveBeenCalled())
    expect(await screen.findByText(/Rupture détectée : maillon n° 17 \(sur 42\)\./)).toBeInTheDocument()
  })

  it('affiche « Chaîne d’audit intacte » quand valide=true', async () => {
    mocks.verifier.mockResolvedValueOnce({
      data: { valide: true, nb_maillons: 42, rupture: null },
    })
    mount()
    const bouton = await screen.findByRole('button', { name: /Vérifier l.intégrité/ })
    fireEvent.click(bouton)

    await waitFor(() => expect(mocks.verifier).toHaveBeenCalled())
    expect(await screen.findByText(
      'Chaîne d’audit intacte — aucune altération détectée.',
    )).toBeInTheDocument()
  })
})
