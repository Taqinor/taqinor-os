// ODY4 — tests des fonctions PURES de résolution « route → app active ».
// (Le rendu de la coquille en immersion est couvert par
// `components/layout/Sidebar.ody4.test.jsx`.)
import { describe, it, expect, beforeEach } from 'vitest'
import { renderHook } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'
import {
  buildAppRouteIndex, resolveAppKey, appNavItems, crossAppTransition,
  ORPHAN_NAV_ITEMS, HOME_MENU_PATH, useActiveApp,
  annoncerBascule, _resetAnnonceForTests,
} from './ActiveAppContext'
import { resumeKey, RESUME_PREFIX, LAST_APP_KEY } from './appPrefs'
import { moduleConfigs } from '../../router/moduleRoutes'

const FIXTURE = [
  {
    key: 'crm',
    nav: { label: 'CRM', items: [{ to: '/crm/leads', label: 'Leads', roles: ['normal', 'admin'] }] },
    routes: [{ path: '/crm/leads/:id' }, { path: '/activites' }],
    sectionLabels: { crm: 'CRM' },
  },
  {
    key: 'ventes',
    nav: {
      label: 'VENTES',
      items: [
        { to: '/ventes/devis', label: 'Devis', roles: ['normal', 'admin'] },
        { to: '/ventes/remises', label: 'Remises', roles: ['admin'], perm: 'remise_valider' },
      ],
    },
    routes: [{ path: '/ventes/devis/nouveau' }],
  },
  {
    // Miroir du cas RÉEL `admin` (routes) vs `parametres` (nav) sur /admin/users.
    key: 'admin',
    routes: [{ path: '/admin/users' }],
  },
  {
    key: 'parametres',
    nav: { label: 'PARAMÈTRES', items: [{ to: '/admin/users', label: 'Utilisateurs', roles: ['admin'] }] },
  },
]

const INDEX = buildAppRouteIndex(FIXTURE)

describe('ODY4 — buildAppRouteIndex / resolveAppKey', () => {
  it('résout un écran vers l’app qui le déclare', () => {
    expect(resolveAppKey(INDEX, '/crm/leads')).toBe('crm')
    expect(resolveAppKey(INDEX, '/ventes/devis')).toBe('ventes')
  })

  it('le préfixe le PLUS LONG gagne (sous-écran d’une app)', () => {
    expect(resolveAppKey(INDEX, '/ventes/devis/nouveau')).toBe('ventes')
    expect(resolveAppKey(INDEX, '/crm/leads/42')).toBe('crm')
  })

  it('les paramètres de route (:id) et la query sont ignorés à l’indexation', () => {
    expect(resolveAppKey(INDEX, '/crm/leads/42/detail')).toBe('crm')
    expect(resolveAppKey(INDEX, '/ventes/devis?new=1')).toBe('ventes')
  })

  it('un item de NAV l’emporte sur une simple route pour le MÊME chemin', () => {
    // Cas réel : /admin/users est une `route` de `admin` mais un item de `nav`
    // de `parametres` (ODY23) → l'app active est celle que le MENU promet.
    expect(resolveAppKey(INDEX, '/admin/users')).toBe('parametres')
  })

  it('comparaison par SEGMENT : /crm ne capture pas /crmXYZ', () => {
    expect(resolveAppKey(INDEX, '/crmXYZ')).toBeNull()
  })

  it('un chemin hors de toute app renvoie null (coquille neutre)', () => {
    expect(resolveAppKey(INDEX, HOME_MENU_PATH)).toBeNull()
    expect(resolveAppKey(INDEX, '/')).toBeNull()
    expect(resolveAppKey(INDEX, '')).toBeNull()
  })

  it('tolère un registre vide ou malformé', () => {
    expect(buildAppRouteIndex(null)).toEqual([])
    expect(buildAppRouteIndex([{}, { key: 'x' }])).toEqual([])
    expect(resolveAppKey(null, '/crm')).toBeNull()
  })
})

describe('ODY4 — appNavItems (rôle + permission)', () => {
  const ventes = FIXTURE[1]

  it('filtre par palier de rôle', () => {
    expect(appNavItems(ventes, 'normal').map((i) => i.to)).toEqual(['/ventes/devis'])
  })

  it('filtre par permission ERP fine', () => {
    expect(appNavItems(ventes, 'admin').map((i) => i.to)).toEqual(['/ventes/devis'])
    expect(appNavItems(ventes, 'admin', ['remise_valider']).map((i) => i.to))
      .toEqual(['/ventes/devis', '/ventes/remises'])
  })

  it('tolère une config absente', () => {
    expect(appNavItems(null, 'admin')).toEqual([])
  })
})

describe('ODY4 — crossAppTransition (ODY7)', () => {
  it('signale une bascule d’app', () => {
    const t = crossAppTransition('/crm/leads/12', '/ventes/devis')
    expect(t).toEqual({ from: 'crm', to: 'ventes', switched: true })
  })

  it('une navigation INTRA-app n’est pas une bascule', () => {
    expect(crossAppTransition('/crm/leads', '/crm').switched).toBe(false)
  })
})

// Le registre RÉEL doit rester cohérent avec le paradigme : chaque item de nav
// d'une app doit être résolu vers UNE app (sinon la coquille disparaîtrait en
// suivant son propre menu), et « Ma file » doit appartenir à CRM.
describe('ODY4 — cohérence du registre réel', () => {
  const realIndex = buildAppRouteIndex(moduleConfigs)

  it('chaque item de nav du registre est résolu vers une app', () => {
    const orphans = []
    moduleConfigs.forEach((c) => {
      ;(c.nav?.items ?? []).forEach((it) => {
        if (typeof it?.to === 'string' && !resolveAppKey(realIndex, it.to)) orphans.push(it.to)
      })
    })
    expect(orphans, `destinations sans app : ${orphans.join(', ')}`).toEqual([])
  })

  it('« Ma file » (/activites) appartient à l’app CRM', () => {
    expect(ORPHAN_NAV_ITEMS.crm.map((i) => i.to)).toContain('/activites')
    expect(resolveAppKey(realIndex, '/activites')).toBe('crm')
  })

  it('le Menu d’accueil n’appartient à AUCUNE app (coquille neutre)', () => {
    expect(resolveAppKey(realIndex, HOME_MENU_PATH)).toBeNull()
  })
})

// ── ODY29 — chaque app se souvient de l'endroit où on l'a quittée ───────────
// L'écriture se fait dans `useActiveApp` : c'est le seul endroit qui connaît
// déjà le couple (route → app). On l'observe donc en montant vraiment le hook.
describe('ODY29 — useActiveApp mémorise la route de reprise', () => {
  function monter(path, { user = null } = {}) {
    const store = configureStore({
      reducer: {
        auth: (s = { role: 'admin', permissions: [], modulesDesactives: [], user }) => s,
      },
    })
    return renderHook(() => useActiveApp(), {
      wrapper: ({ children }) => (
        <Provider store={store}>
          <MemoryRouter initialEntries={[path]}>{children}</MemoryRouter>
        </Provider>
      ),
    })
  }

  beforeEach(() => {
    window.sessionStorage.clear()
  })

  it('mémorise la route courante sous la clé de son app', () => {
    monter('/crm/leads')
    expect(window.sessionStorage.getItem(resumeKey('crm', null))).toBe('/crm/leads')
  })

  it('la clé porte l’utilisateur : une session n’écrase pas celle d’un autre', () => {
    monter('/ventes/devis', { user: { id: 7 } })
    expect(window.sessionStorage.getItem(resumeKey('ventes', 7))).toBe('/ventes/devis')
    expect(window.sessionStorage.getItem(resumeKey('ventes', 8))).toBeNull()
  })

  it('un écran hors de toute app (Menu d’accueil) n’écrit RIEN', () => {
    monter(HOME_MENU_PATH)
    const cles = []
    for (let i = 0; i < window.sessionStorage.length; i += 1) {
      cles.push(window.sessionStorage.key(i))
    }
    expect(cles.filter((k) => k.startsWith(RESUME_PREFIX))).toEqual([])
  })

  it('ODY32 — mémorise aussi l’app quittée, pour le retour de focus', () => {
    monter('/sav')
    expect(window.sessionStorage.getItem(LAST_APP_KEY)).toBe('sav')
  })

  it('une app désactivée pour la société n’écrit rien non plus', () => {
    const store = configureStore({
      reducer: {
        auth: (s = {
          role: 'admin', permissions: [], modulesDesactives: ['crm'], user: null,
        }) => s,
      },
    })
    renderHook(() => useActiveApp(), {
      wrapper: ({ children }) => (
        <Provider store={store}>
          <MemoryRouter initialEntries={['/crm/leads']}>{children}</MemoryRouter>
        </Provider>
      ),
    })
    expect(window.sessionStorage.getItem(resumeKey('crm', null))).toBeNull()
  })
})

// ── ODY32 — annonce DISCRÈTE de la bascule d'app ────────────────────────────
// La règle tient en une phrase : cette région ne parle que quand on change
// d'APPLICATION. `RouteFocus` (VX197) annonce déjà le nom d'écran à chaque
// navigation — on ne double jamais ce canal.
describe('ODY32 — annonce de bascule d’app', () => {
  const region = () => document.getElementById('taqinor-app-annonce')

  beforeEach(() => {
    _resetAnnonceForTests()
  })

  it('la toute première résolution ne dit RIEN (chargement direct, F5)', () => {
    expect(annoncerBascule('crm', 'CRM')).toBe(false)
    expect(region()).toBeNull()
  })

  it('un vrai changement d’app est annoncé une fois, poliment', () => {
    annoncerBascule(null, '') // le Menu d'accueil : 1re résolution
    expect(annoncerBascule('ventes', 'VENTES')).toBe(true)
    expect(region()).not.toBeNull()
    expect(region().getAttribute('aria-live')).toBe('polite')
    expect(region().className).toContain('sr-only')
    expect(region().textContent).toBe('Application VENTES')
  })

  it('naviguer DANS la même app ne dit rien (pas de doublon de RouteFocus)', () => {
    annoncerBascule(null, '')
    annoncerBascule('ventes', 'VENTES')
    expect(annoncerBascule('ventes', 'VENTES')).toBe(false)
    expect(region().textContent).toBe('Application VENTES')
  })

  it('ressortir au Menu d’accueil ne dit rien non plus', () => {
    annoncerBascule(null, '')
    annoncerBascule('ventes', 'VENTES')
    expect(annoncerBascule(null, '')).toBe(false)
    // …mais l'app suivante est bien annoncée : l'état a suivi la sortie.
    expect(annoncerBascule('crm', 'CRM')).toBe(true)
    expect(region().textContent).toBe('Application CRM')
  })

  it('une seule région pour toute la page, quel que soit le nombre d’appels', () => {
    annoncerBascule(null, '')
    annoncerBascule('crm', 'CRM')
    annoncerBascule('ventes', 'VENTES')
    expect(document.querySelectorAll('#taqinor-app-annonce')).toHaveLength(1)
  })
})
