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
  // ADOC120 — un client du portail ne voit jamais l'accueil de la marque ERP.
  it('compte portail : pas de bienvenue ERP', () => {
    for (const portee of ['portail_client', 'portail_fournisseur', 'portail_partenaire']) {
      renderWith({ username: 'client-294', portee })
      expect(screen.queryByText(/Bienvenue chez Taqinor/i)).not.toBeInTheDocument()
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
      cleanup()
    }
    // et rien n'est marqué « vu » : pas de pollution du flag interne.
    expect(window.localStorage.getItem('taqinor:welcome:seen:v1')).toBeNull()
  })

  it('utilisateur interne explicite : bienvenue inchangée', async () => {
    renderWith({ username: 'reda', portee: 'interne' })
    expect(await screen.findByText(/Bienvenue chez Taqinor/i)).toBeInTheDocument()
  })

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
