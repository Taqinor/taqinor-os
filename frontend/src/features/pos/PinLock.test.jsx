import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* NTRET3 — smoke de PinLock (API mockée, hors réseau) : PIN correct
   déverrouille (onUnlock appelé avec l'utilisateur), PIN erroné affiche une
   erreur sans démonter l'overlay, le caissier actif est mémorisé. */

const postMock = vi.fn()
vi.mock('../../api/axios', () => ({
  default: { post: (...args) => postMock(...args) },
}))

import PinLock, { lireCaissierActif, memoriserCaissierActif } from './PinLock'

beforeEach(() => {
  postMock.mockReset()
  window.localStorage.clear()
})

describe('PinLock', () => {
  it('PIN correct appelle onUnlock avec l’utilisateur renvoyé par le serveur', async () => {
    postMock.mockResolvedValue({ data: { id: 5, username: 'caissier2' } })
    const onUnlock = vi.fn()
    const user = userEvent.setup()
    render(<PinLock userId={5} onUnlock={onUnlock} />)

    await user.type(screen.getByLabelText(/PIN/), '1234')
    await user.click(screen.getByRole('button', { name: /Déverrouiller/ }))

    await waitFor(() => expect(onUnlock).toHaveBeenCalledWith({ id: 5, username: 'caissier2' }))
    expect(postMock).toHaveBeenCalledWith('/pos/verifier-pin/', {
      user_id: 5, pin: '1234', caissier_precedent: null,
    })
    expect(lireCaissierActif()).toEqual({ id: 5, username: 'caissier2' })
  })

  it('PIN erroné n’appelle jamais onUnlock', async () => {
    const err = new Error('rejected')
    err.response = { data: { detail: 'PIN incorrect.' } }
    postMock.mockRejectedValue(err)
    const onUnlock = vi.fn()
    const user = userEvent.setup()
    render(<PinLock userId={5} onUnlock={onUnlock} />)

    await user.type(screen.getByLabelText(/PIN/), '0000')
    await user.click(screen.getByRole('button', { name: /Déverrouiller/ }))

    await waitFor(() => expect(postMock).toHaveBeenCalled())
    expect(onUnlock).not.toHaveBeenCalled()
    expect(screen.getByTestId('pin-lock-overlay')).toBeInTheDocument()
  })

  it('transmet le caissier précédemment actif pour la journalisation serveur', async () => {
    memoriserCaissierActif({ id: 1, username: 'caissier1' })
    postMock.mockResolvedValue({ data: { id: 2, username: 'caissier2' } })
    const user = userEvent.setup()
    render(<PinLock userId={2} onUnlock={() => {}} />)

    await user.type(screen.getByLabelText(/PIN/), '2222')
    await user.click(screen.getByRole('button', { name: /Déverrouiller/ }))

    await waitFor(() => expect(postMock).toHaveBeenCalledWith('/pos/verifier-pin/', {
      user_id: 2, pin: '2222', caissier_precedent: 1,
    }))
  })

  it('verrouille=false ne rend rien', () => {
    render(<PinLock userId={1} onUnlock={() => {}} verrouille={false} />)
    expect(screen.queryByTestId('pin-lock-overlay')).not.toBeInTheDocument()
  })
})
