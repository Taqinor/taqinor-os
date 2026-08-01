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
} from './ActiveAppContext'
import { resumeKey, RESUME_PREFIX } from './appPrefs'
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
    const clesDeReprise = Object.keys(window.sessionStorage)
      .filter((k) => k.startsWith(RESUME_PREFIX))
    expect(clesDeReprise).toEqual([])
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
