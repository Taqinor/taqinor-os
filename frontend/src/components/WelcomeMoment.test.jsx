import { describe, it, expect, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import WelcomeMoment from './WelcomeMoment'

/* VX156 — accueil one-shot : affiché à la première connexion, plus jamais après
   (flag localStorage), et jamais avant qu'un utilisateur soit connecté. */

function renderWith(user) {
  const store = configureStore({ reducer: { auth: (s = { user }) => s } })
  return render(
    <Provider store={store}>
      <WelcomeMoment />
    </Provider>,
  )
}

afterEach(() => {
  cleanup()
  try { window.localStorage.clear() } catch { /* noop */ }
})

describe('VX156 — WelcomeMoment', () => {
  it('affiché à la première connexion puis plus jamais', async () => {
    renderWith({ username: 'reda' })
    expect(await screen.findByText(/Bienvenue chez Taqinor/i)).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Commencer' }))
    expect(screen.queryByText(/Bienvenue chez Taqinor/i)).not.toBeInTheDocument()

    // Un remontage (nouvelle session d'app) ne le réaffiche pas : le flag tient.
    cleanup()
    renderWith({ username: 'reda' })
    expect(screen.queryByText(/Bienvenue chez Taqinor/i)).not.toBeInTheDocument()
  })

  it('ne s’affiche pas tant qu’aucun utilisateur n’est connecté', () => {
    renderWith(undefined)
    expect(screen.queryByText(/Bienvenue chez Taqinor/i)).not.toBeInTheDocument()
  })
})
