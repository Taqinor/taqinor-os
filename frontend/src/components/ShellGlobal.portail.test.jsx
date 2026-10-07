import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'

/* ADOC146 — GARDE DE CLASSE « shell global portail ». ShellGlobal rend les
   composants montés hors du RouterProvider ; pour un compte de CHAQUE portée
   portail, aucun d'eux ne doit appeler un endpoint INTERNE (hors /auth/ et
   /portail/, sauf la lecture silencieuse des surcharges de traduction) ni
   afficher un toast ou une modale. Le serveur de test répond 403 à tout chemin
   hors liste blanche (comme la sonde #LIVE1). Un composant ajouté plus tard à
   ShellGlobal entre automatiquement dans ce balayage. */

const { appels } = vi.hoisted(() => ({ appels: [] }))

vi.mock('../api/axios', () => {
  const repondre = (verbe) => (url, ...reste) => {
    appels.push({ verbe, url, options: reste[reste.length - 1] })
    const autorise = /^\/(auth|portail)\//.test(url)
      || (url === '/parametres/traductions/effective/'
        && reste[reste.length - 1]?.suppressErrorToast === true)
    if (autorise) return Promise.resolve({ data: {} })
    return Promise.reject({
      response: { status: 403, data: { detail: "Vous n'avez pas la permission" } },
    })
  }
  return {
    default: {
      get: repondre('get'),
      post: repondre('post'),
      put: repondre('put'),
      patch: repondre('patch'),
      delete: repondre('delete'),
    },
  }
})
// Le message d'accueil est monté hors routeur : `router.navigate` n'est pas utilisé ici.
vi.mock('../router', () => ({ default: { navigate: vi.fn() } }))
// Toaster dépend d'un ThemeProvider (hors périmètre de ce test).
vi.mock('../design/theme-context', () => ({
  useTheme: () => ({ resolvedTheme: 'light' }),
}))

import { I18nProvider } from '../i18n'
import ShellGlobal from './ShellGlobal'

const PORTEES = ['portail_client', 'portail_fournisseur', 'portail_partenaire']

function rendre(user) {
  const store = configureStore({
    reducer: { auth: (s = { isAuthenticated: true, user }) => s },
  })
  return render(
    <Provider store={store}>
      <I18nProvider chargerSurcharges={false}>
        <ShellGlobal />
      </I18nProvider>
    </Provider>,
  )
}

// Laisse passer le chargement lazy de MessageAccueilModal + les effets.
async function stabiliser() {
  await new Promise((r) => setTimeout(r, 50))
}

beforeEach(() => {
  appels.length = 0
  try { window.localStorage.clear() } catch { /* noop */ }
})
afterEach(() => cleanup())

describe('ADOC146 — ShellGlobal pour un compte portail', () => {
  for (const portee of PORTEES) {
    it(`${portee} : aucun endpoint interne, aucun toast, aucune modale`, async () => {
      rendre({ username: `compte-${portee}`, portee, langue_interface: 'fr' })
      await stabiliser()

      const interdits = appels.filter(({ url, options }) => {
        if (/^\/(auth|portail)\//.test(url)) return false
        if (url === '/parametres/traductions/effective/'
          && options?.suppressErrorToast === true) return false
        return true
      })
      expect(interdits).toEqual([])
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
      expect(document.querySelector('[data-sonner-toast]')).toBeNull()
      expect(screen.queryByText(/Bienvenue chez Taqinor/i)).not.toBeInTheDocument()
    })
  }

  it('contrôle : un compte interne garde le comportement actuel (accueil + lecture des messages)', async () => {
    rendre({ username: 'demo_admin', portee: 'interne', langue_interface: 'fr' })
    await waitFor(() => expect(
      appels.some(({ url }) => url === '/notifications/messages-accueil/a-lire/'),
    ).toBe(true))
    expect(await screen.findByText(/Bienvenue chez Taqinor/i)).toBeInTheDocument()
  })
})
