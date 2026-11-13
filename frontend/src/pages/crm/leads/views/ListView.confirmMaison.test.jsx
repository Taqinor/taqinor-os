import { describe, it, expect, vi, beforeAll, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, cleanup, fireEvent } from '@testing-library/react'
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

const { deleteLead, archiverLead, toastError, toastWithUndo } = vi.hoisted(() => ({
  deleteLead: vi.fn(),
  archiverLead: vi.fn(),
  toastError: vi.fn(),
  toastWithUndo: vi.fn(),
}))
vi.mock('../../../../api/crmApi', () => ({
  default: {
    deleteLead: (...a) => deleteLead(...a), restaurerCorbeille: vi.fn(),
    archiverLead: (...a) => archiverLead(...a),
  },
}))
vi.mock('../../../../lib/toast', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    toastError: (...a) => toastError(...a),
    toastWithUndo: (...a) => toastWithUndo(...a),
  }
})

import ListView from './ListView'
import { SIGNE_INTERCEPT } from '../signeIntercept'
import { polyfillResizeObserver } from '../../../../test/selectNatif'

beforeAll(polyfillResizeObserver)

const LEAD = {
  id: 9, nom: 'Benali', prenom: 'Aziz', stage: 'NEW', is_archived: false,
  date_creation: '2026-09-01T10:00:00Z', score: 10, devis: [], tags: [],
}

function rendre({ lead = LEAD, onInlineSave } = {}) {
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
            <ListView leads={[lead]} onRefetch={vi.fn()} onInlineSave={onInlineSave} />
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

describe('AERR113 — ListView : archiver/supprimer nomment le lead', () => {
  it('Archiver depuis la liste : confirmation qui nomme le lead', async () => {
    archiverLead.mockResolvedValue({ data: { ...LEAD, is_archived: true } })
    const user = userEvent.setup()
    rendre()
    await user.click(await screen.findByRole('button', { name: 'Archiver' }))
    let dialogue = await screen.findByRole('alertdialog')
    expect(dialogue).toHaveTextContent('Archiver « Aziz Benali » ?')
    await user.click([...dialogue.querySelectorAll('button')]
      .find((b) => b.textContent.trim() === 'Annuler'))
    await waitFor(() => expect(screen.queryByRole('alertdialog')).toBeNull())
    expect(archiverLead).not.toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: 'Archiver' }))
    dialogue = await screen.findByRole('alertdialog')
    await user.click([...dialogue.querySelectorAll('button')]
      .find((b) => b.textContent.trim() === 'Archiver'))
    await waitFor(() => expect(archiverLead).toHaveBeenCalledWith(9))
    expect(archiverLead).toHaveBeenCalledTimes(1)
  })

  it('Supprimer : la boîte nomme le lead', async () => {
    const user = userEvent.setup()
    rendre()
    await user.click(await screen.findByRole('button', { name: 'Supprimer' }))
    expect(await screen.findByRole('alertdialog')).toHaveTextContent('Aziz Benali')
  })
})

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

/* ERR-W33-INLINE-STAGE — la cellule Stade passe par l'enveloppe d'undo : ses
   marqueurs doivent atteindre l'enregistrement (sinon 409 après que
   l'utilisatrice a choisi sa raison), et l'annulation doit porter `undo`. */
describe('ListView : marqueurs de la cellule Stade à travers l’undo', () => {
  const choisirEtape = async (user, etape) => {
    await user.click(screen.getByRole('button', { name: /Nouveau|Contacté/ }))
    const select = document.querySelector('select.ie-input')
    fireEvent.change(select, { target: { value: etape } })
    fireEvent.blur(select)
  }

  it('Froid : la raison choisie part avec le PATCH, sans « Annuler »', async () => {
    const onInlineSave = vi.fn(() => Promise.resolve({}))
    const user = userEvent.setup()
    rendre({ onInlineSave })
    await choisirEtape(user, 'COLD')
    const bouton = await screen.findByRole('button', { name: 'Mettre au Froid' })
    fireEvent.change(screen.getByLabelText('Raison de mise au Froid'), { target: { value: 'budget' } })
    fireEvent.click(bouton)
    await waitFor(() => expect(onInlineSave).toHaveBeenCalledWith(
      LEAD, 'stage', 'COLD', expect.objectContaining({ parcRaison: 'budget' })))
    expect(toastWithUndo).not.toHaveBeenCalled()
  })

  it('avancée : « Annuler » renvoie l’étape d’avant avec le marqueur undo', async () => {
    const onInlineSave = vi.fn(() => Promise.resolve({}))
    const user = userEvent.setup()
    rendre({ onInlineSave })
    await choisirEtape(user, 'CONTACTED')
    await waitFor(() => expect(toastWithUndo).toHaveBeenCalled())
    expect(onInlineSave).toHaveBeenCalledWith(
      LEAD, 'stage', 'CONTACTED', { confirmeRecul: false, parcRaison: undefined })
    await toastWithUndo.mock.calls[0][0].onUndo()
    expect(onInlineSave).toHaveBeenLastCalledWith(LEAD, 'stage', 'NEW', { undo: true })
  })

  it('« Signé » : le dialogue s’ouvre sans faux toast d’erreur', async () => {
    const onInlineSave = vi.fn(() => Promise.reject(SIGNE_INTERCEPT))
    const user = userEvent.setup()
    rendre({ onInlineSave })
    await choisirEtape(user, 'SIGNED')
    await waitFor(() => expect(onInlineSave).toHaveBeenCalled())
    expect(toastError).not.toHaveBeenCalled()
    expect(toastWithUndo).not.toHaveBeenCalled()
  })
})
