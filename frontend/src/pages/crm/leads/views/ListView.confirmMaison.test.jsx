import { describe, it, expect, vi, beforeAll, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../../../design/ThemeProvider'
import { ConfirmProvider } from '../../../../providers/ConfirmProvider'
import crmReducer from '../../../../features/crm/store/crmSlice'

/* ALEA22 — la suppression d'un lead passe par le dialogue de confirmation
   MAISON (jamais `window.confirm`), et l'échec 409 « lead lié à un devis »
   s'affiche dans un toast (jamais `window.alert`). Réducteur et vue RÉELS ;
   seul l'appel réseau `crmApi.deleteLead` est simulé. */

const { deleteLead, toastError } = vi.hoisted(() => ({
  deleteLead: vi.fn(),
  toastError: vi.fn(),
}))
vi.mock('../../../../api/crmApi', () => ({
  default: { deleteLead: (...a) => deleteLead(...a), restaurerCorbeille: vi.fn() },
}))
vi.mock('../../../../lib/toast', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, toastError: (...a) => toastError(...a) }
})

import ListView from './ListView'

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
  }
})

const LEAD = {
  id: 9, nom: 'Benali', prenom: 'Aziz', stage: 'NEW', is_archived: false,
  date_creation: '2026-09-01T10:00:00Z', score: 10, devis: [], tags: [],
}

function rendre() {
  const store = configureStore({
    reducer: {
      crm: crmReducer,
      auth: (s = { role: 'admin', permissions: [], user: { id: 1 } }) => s,
    },
  })
  return render(
    <Provider store={store}>
      <ThemeProvider>
        <MemoryRouter>
          <ConfirmProvider>
            <ListView leads={[LEAD]} onRefetch={vi.fn()} />
          </ConfirmProvider>
        </MemoryRouter>
      </ThemeProvider>
    </Provider>,
  )
}

let confirmNatif
let alertNatif
beforeEach(() => {
  vi.clearAllMocks()
  confirmNatif = vi.spyOn(window, 'confirm').mockReturnValue(true)
  alertNatif = vi.spyOn(window, 'alert').mockImplementation(() => {})
})
afterEach(() => { cleanup(); vi.restoreAllMocks() })

describe('ALEA22 — ListView : confirmation maison', () => {
  it('Supprimer → dialogue maison rendu, aucun window.confirm', async () => {
    deleteLead.mockResolvedValue({ data: { corbeille_id: 3 } })
    const user = userEvent.setup()
    rendre()
    await user.click(await screen.findByRole('button', { name: 'Supprimer' }))
    const dialogue = await screen.findByRole('alertdialog')
    expect(dialogue).toHaveTextContent(/Supprimer ce lead/)
    expect(confirmNatif).not.toHaveBeenCalled()
    expect(deleteLead).not.toHaveBeenCalled()
    const bouton = [...dialogue.querySelectorAll('button')]
      .find((b) => b.textContent.trim() === 'Supprimer')
    await user.click(bouton)
    await waitFor(() => expect(deleteLead).toHaveBeenCalledWith(9))
  })

  it('Annuler dans le dialogue → rien n’est supprimé', async () => {
    const user = userEvent.setup()
    rendre()
    await user.click(await screen.findByRole('button', { name: 'Supprimer' }))
    const dialogue = await screen.findByRole('alertdialog')
    await user.click([...dialogue.querySelectorAll('button')]
      .find((b) => b.textContent.trim() === 'Annuler'))
    await waitFor(() => expect(screen.queryByRole('alertdialog')).toBeNull())
    expect(deleteLead).not.toHaveBeenCalled()
  })

  it('409 « lead lié à un devis » → toast d’erreur, aucun window.alert', async () => {
    deleteLead.mockRejectedValue({
      response: { status: 409, data: { detail: 'Ce lead est lié à un devis.' } },
    })
    const user = userEvent.setup()
    rendre()
    await user.click(await screen.findByRole('button', { name: 'Supprimer' }))
    const dialogue = await screen.findByRole('alertdialog')
    await user.click([...dialogue.querySelectorAll('button')]
      .find((b) => b.textContent.trim() === 'Supprimer'))
    await waitFor(() => expect(toastError).toHaveBeenCalled())
    expect(alertNatif).not.toHaveBeenCalled()
  })
})
