import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'

/* ADOC146 — GARDE DE CLASSE « shell global portail ». ShellGlobal rend les
   composants montés hors du RouterProvider ; pour un compte de CHAQUE portée
   portail, aucun d'eux ne doit appeler un endpoint INTERNE (hors /auth/ et
   /portail/, sauf la lecture silencieuse des surcharges de traduction) ni
   afficher un toast ou une modale. Le serveur de test répond 403 à tout chemin
   hors liste blanche (comme la sonde #LIVE1). Un composant ajouté plus tard à
   ShellGlobal entre automatiquement dans ce balayage. */

const { appels, sante, sw } = vi.hoisted(() => ({
  appels: [], sante: { tri: null }, sw: { needRefresh: false, update: vi.fn() },
}))

// BPQ7 — `virtual:pwa-register/react` : état « nouvelle version prête » piloté par le test.
vi.mock('virtual:pwa-register/react', () => ({
  useRegisterSW: () => ({
    needRefresh: [sw.needRefresh, vi.fn()],
    offlineReady: [false, vi.fn()],
    updateServiceWorker: sw.update,
  }),
}))

vi.mock('../api/axios', () => {
  const repondre = (verbe) => (url, ...reste) => {
    appels.push({ verbe, url, options: reste[reste.length - 1] })
    const autorise = /^\/(auth|portail)\//.test(url)
      || (url === '/parametres/traductions/effective/'
        && reste[reste.length - 1]?.suppressErrorToast === true)
    if (url === '/core/health/ready/') {
      if (sante.code503) {
        return Promise.reject({ response: { status: 503, data: { status: 'degraded', dernier_tri_problemes: sante.tri } } })
      }
      return Promise.resolve({
        data: sante.sansCle ? { status: 'ready' } : { status: 'ready', dernier_tri_problemes: sante.tri },
      })
    }
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
  sante.tri = null
  sante.sansCle = false
  sante.code503 = false
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

describe('BPQ6 — bandeau du tri quotidien des problèmes', () => {
  const ilYa = (h) => new Date(Date.now() - h * 3600000).toISOString()

  it("superuser : bandeau au-delà de 48 h, avec le nombre d'heures", async () => {
    sante.tri = ilYa(60)
    rendre({ username: 'root', portee: 'interne', is_superuser: true, langue_interface: 'fr' })
    expect(await screen.findByText(/n'a pas tourné depuis 60 h/)).toBeInTheDocument()
    expect(appels.filter(({ url }) => url === '/core/health/ready/')).toHaveLength(1)
  })

  it('superuser : rien avant 48 h', async () => {
    sante.tri = ilYa(20)
    rendre({ username: 'root', portee: 'interne', is_superuser: true, langue_interface: 'fr' })
    await stabiliser()
    expect(screen.queryByTestId('bandeau-tri-problemes')).toBeNull()
  })

  it('superuser : bandeau « jamais tourné » si dernier_tri_problemes est null, rien si la clé manque', async () => {
    sante.tri = null
    rendre({ username: 'root', portee: 'interne', is_superuser: true, langue_interface: 'fr' })
    expect(await screen.findByText("Le tri quotidien des problèmes n'a jamais tourné.")).toBeInTheDocument()
    cleanup()
    sante.code503 = true // beat arrêté : 503 « degraded », le corps garde la clé
    rendre({ username: 'root', portee: 'interne', is_superuser: true, langue_interface: 'fr' })
    expect(await screen.findByTestId('bandeau-tri-problemes')).toBeInTheDocument()
    cleanup()
    sante.code503 = false
    sante.sansCle = true
    rendre({ username: 'root', portee: 'interne', is_superuser: true, langue_interface: 'fr' })
    await stabiliser()
    expect(screen.queryByTestId('bandeau-tri-problemes')).toBeNull()
  })

  it('non-superuser : ni appel ni bandeau', async () => {
    sante.tri = ilYa(100)
    rendre({ username: 'demo_admin', portee: 'interne', is_superuser: false, langue_interface: 'fr' })
    await stabiliser()
    expect(appels.some(({ url }) => url === '/core/health/ready/')).toBe(false)
    expect(screen.queryByTestId('bandeau-tri-problemes')).toBeNull()
  })
})

describe('BPQ7 — bandeau « Nouvelle version » dans le shell', () => {
  it('rien tant qu’aucune version n’est prête', async () => {
    sw.needRefresh = false
    rendre({ username: 'demo_admin', portee: 'interne', langue_interface: 'fr' })
    await stabiliser()
    expect(screen.queryByTestId('ae-update-banner')).toBeNull()
  })

  it('version prête : un seul bandeau, « Recharger » demande skipWaiting (updateServiceWorker(true))', async () => {
    sw.needRefresh = true
    sw.update.mockClear()
    rendre({ username: 'demo_admin', portee: 'interne', langue_interface: 'fr' })
    expect(await screen.findAllByTestId('ae-update-banner')).toHaveLength(1)
    fireEvent.click(screen.getByTestId('ae-update-banner-reload'))
    expect(sw.update).toHaveBeenCalledWith(true)
    sw.needRefresh = false
  })
})
