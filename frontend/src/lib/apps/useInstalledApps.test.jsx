// ODY1 — Tests de la source unique « mes apps ».
//   • `buildInstalledApps` (fonction pure) : matrice registre × modules
//     désactivés (ODX6) × rôle/permission (ARC47), avec des configs fabriquées
//     (indépendantes du registre réel — comportement isolé et déterministe).
//   • `useInstalledApps` (hook) : câblage Redux réel (store minimal, comme
//     BottomTabBar.test.jsx/Sidebar.test.jsx) sur un registre `moduleConfigs`
//     mocké, pour vérifier que le hook réagit bien à `modulesDesactives`/
//     `role`/`permissions`.
import { describe, it, expect, vi } from 'vitest'
import { renderHook } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import React from 'react'

// Registre mocké — reprend la FORME réelle de moduleConfigs (router/
// moduleRoutes.jsx). vi.mock est hoisté au-dessus des imports (comme
// useApprobationsCount.test.jsx) : le hook importé plus bas verra ce registre.
vi.mock('../../router/moduleRoutes', () => ({
  moduleConfigs: [
    {
      key: 'crm',
      order: 40,
      nav: {
        label: 'CRM',
        accent: 'azur',
        items: [{ to: '/crm', label: 'Clients', icon: 'icon-crm', roles: ['normal', 'responsable', 'admin'] }],
      },
    },
    {
      key: 'admin-only-app',
      order: 95,
      nav: {
        label: 'ADMIN SEUL',
        items: [{ to: '/admin-seul', label: 'Écran', icon: 'icon-admin', roles: ['admin'] }],
      },
    },
  ],
}))

import useInstalledApps, {
  buildInstalledApps, allowedAppKeys, appVisibilityPermission,
  isAppVisibilityPermission,
} from './useInstalledApps'

const iconClients = <span data-testid="icon-clients" />
const iconLeads = <span data-testid="icon-leads" />
const iconDevis = <span data-testid="icon-devis" />
const iconActionRequise = <span data-testid="icon-action-requise" />

// Configs fabriquées pour `buildInstalledApps` — reprend la FORME réelle de
// moduleConfigs : { key, nav: { label, accent, items: [{to,label,icon,roles,
// perm}] } }, plus un module routes-only (comme `admin` en vrai) et un module
// sans nav ni routes (comme `ao` en vrai).
function makeConfigs() {
  return [
    {
      key: 'crm',
      order: 40,
      nav: {
        label: 'CRM',
        accent: 'azur',
        items: [
          { to: '/crm', label: 'Clients', icon: iconClients, roles: ['normal', 'responsable', 'admin'] },
          { to: '/crm/leads', label: 'Leads', icon: iconLeads, roles: ['responsable', 'admin'] },
        ],
      },
    },
    {
      key: 'ventes',
      order: 50,
      nav: {
        label: 'VENTES',
        accent: 'brass',
        items: [
          // 1er item volontairement réservé responsable/admin : le rôle
          // 'normal' doit retomber sur le 2e item (Devis), jamais un lien mort.
          { to: '/ventes/devis/action-requise', label: 'Action requise', icon: iconActionRequise, roles: ['responsable', 'admin'] },
          { to: '/ventes/devis', label: 'Devis', icon: iconDevis, roles: ['normal', 'responsable', 'admin'] },
        ],
      },
    },
    // Routes-only (comme `admin` en vrai) : jamais une "app".
    { key: 'admin', order: 80, routes: [{ path: '/admin/users' }] },
    // Sans nav ni routes (comme `ao` en vrai) : jamais une "app".
    { key: 'ao', order: 56 },
    // `nav` présent mais `items` vide : jamais une "app" non plus.
    { key: 'vide', order: 90, nav: { label: 'VIDE', items: [] } },
    // Réservé admin only, pour la matrice rôle.
    {
      key: 'admin-only-app',
      order: 95,
      nav: {
        label: 'ADMIN SEUL',
        accent: 'nuit',
        items: [{ to: '/admin-seul', label: 'Écran', icon: iconClients, roles: ['admin'] }],
      },
    },
  ]
}

describe('buildInstalledApps (ODY1) — registre ∩ modules actifs ∩ rôle', () => {
  it('un rôle admin sans désactivation voit CRM, Ventes et Admin seul (pas les routes-only/sans-écran/vides)', () => {
    const apps = buildInstalledApps(makeConfigs(), { disabledModules: [], role: 'admin', permissions: [] })
    expect(apps.map((a) => a.key)).toEqual(['crm', 'ventes', 'admin-only-app'])
  })

  it('module désactivé (ODX6) disparaît, quel que soit le rôle', () => {
    const apps = buildInstalledApps(makeConfigs(), { disabledModules: ['crm'], role: 'admin', permissions: [] })
    expect(apps.map((a) => a.key)).not.toContain('crm')
    expect(apps.map((a) => a.key)).toContain('ventes')
  })

  it("rôle insuffisant pour TOUS les items de l'app → app absente (pas de tuile vide)", () => {
    const apps = buildInstalledApps(makeConfigs(), { disabledModules: [], role: 'normal', permissions: [] })
    expect(apps.map((a) => a.key)).not.toContain('admin-only-app')
  })

  it("le rôle admin voit l'app admin-only", () => {
    const apps = buildInstalledApps(makeConfigs(), { disabledModules: [], role: 'admin', permissions: [] })
    expect(apps.map((a) => a.key)).toContain('admin-only-app')
  })

  it("« to » et « icon » viennent du PREMIER item VISIBLE, jamais d'un item hors rôle", () => {
    const apps = buildInstalledApps(makeConfigs(), { disabledModules: [], role: 'normal', permissions: [] })
    const ventes = apps.find((a) => a.key === 'ventes')
    expect(ventes.to).toBe('/ventes/devis') // pas '/ventes/devis/action-requise' (hors rôle normal)
    expect(ventes.icon).toBe(iconDevis)
  })

  it('un rôle plus large (responsable) retrouve le 1er item déclaré', () => {
    const apps = buildInstalledApps(makeConfigs(), { disabledModules: [], role: 'responsable', permissions: [] })
    const ventes = apps.find((a) => a.key === 'ventes')
    expect(ventes.to).toBe('/ventes/devis/action-requise')
  })

  it('reprend label FR et accent (VX8) déclarés par le module.config', () => {
    const apps = buildInstalledApps(makeConfigs(), { disabledModules: [], role: 'admin', permissions: [] })
    const crm = apps.find((a) => a.key === 'crm')
    expect(crm.label).toBe('CRM')
    expect(crm.accent).toBe('azur')
  })

  it('description à vide par défaut (aucun module.config ne la déclare encore)', () => {
    const apps = buildInstalledApps(makeConfigs(), { disabledModules: [], role: 'admin', permissions: [] })
    expect(apps.every((a) => a.description === '')).toBe(true)
  })

  it('un item avec `perm` exige la permission ERP en plus du rôle', () => {
    const configs = [{
      key: 'journal',
      nav: {
        label: 'JOURNAL',
        items: [{ to: '/journal', label: 'Journal', icon: iconClients, roles: ['normal', 'responsable', 'admin'], perm: 'journal_activite_voir' }],
      },
    }]
    const sansPerm = buildInstalledApps(configs, { disabledModules: [], role: 'normal', permissions: [] })
    expect(sansPerm).toEqual([])
    const avecPerm = buildInstalledApps(configs, { disabledModules: [], role: 'normal', permissions: ['journal_activite_voir'] })
    expect(avecPerm.map((a) => a.key)).toEqual(['journal'])
  })

  it('liste vide si aucun config fourni', () => {
    expect(buildInstalledApps([], { disabledModules: [], role: 'admin', permissions: [] })).toEqual([])
    expect(buildInstalledApps(undefined, { role: 'admin' })).toEqual([])
  })
})

// --- useInstalledApps (hook) — câblage Redux réel sur le registre mocké ----
function makeStore({ role = 'normal', permissions = [], modulesDesactives = [] } = {}) {
  return configureStore({
    reducer: { auth: (s = { role, permissions, modulesDesactives, user: null }) => s },
  })
}

function renderInstalledApps(opts) {
  const wrapper = ({ children }) => <Provider store={makeStore(opts)}>{children}</Provider>
  return renderHook(() => useInstalledApps(), { wrapper })
}

describe('useInstalledApps (ODY1) — câblage Redux', () => {
  it('rôle normal : voit CRM, pas ADMIN SEUL', () => {
    const { result } = renderInstalledApps({ role: 'normal' })
    expect(result.current.map((a) => a.key)).toEqual(['crm'])
  })

  it('rôle admin : voit les deux', () => {
    const { result } = renderInstalledApps({ role: 'admin' })
    expect(result.current.map((a) => a.key)).toEqual(['crm', 'admin-only-app'])
  })

  it('module CRM désactivé (modulesDesactives) : disparaît même pour un admin', () => {
    const { result } = renderInstalledApps({ role: 'admin', modulesDesactives: ['crm'] })
    expect(result.current.map((a) => a.key)).toEqual(['admin-only-app'])
  })
})

/* ODY26 — axe « App visible » par rôle, porté par `Role.permissions` (décision
   documentée : aucun nouveau champ backend). Le filtre vit DANS ce hook, donc
   les trois surfaces qui le consomment — grille d'accueil (ODY2), navigation
   et lanceur (VX9/épinglés VX10), plus les surfaces transverses ODY27 — sont
   couvertes par construction : aucune ne tient sa propre liste. */
describe('allowedAppKeys / isAppVisibilityPermission (ODY26)', () => {
  it('fabrique et reconnaît un code app_<clé>_voir', () => {
    expect(appVisibilityPermission('crm')).toBe('app_crm_voir')
    expect(appVisibilityPermission('gestion_projet')).toBe('app_gestion_projet_voir')
    expect(isAppVisibilityPermission('app_gestion_projet_voir')).toBe(true)
  })

  it('ne confond JAMAIS un code métier existant avec un marqueur d’app', () => {
    ;['crm_voir', 'sav_voir', 'journal_activite_voir', 'app_voir', 'roles_gerer']
      .forEach((code) => expect(isAppVisibilityPermission(code)).toBe(false))
  })

  it('aucun marqueur → `null` (pas de restriction), jamais un ensemble vide', () => {
    expect(allowedAppKeys([])).toBeNull()
    expect(allowedAppKeys(['crm_voir', 'ventes_creer'])).toBeNull()
    expect(allowedAppKeys(undefined)).toBeNull()
  })

  it('au moins un marqueur → liste blanche des clés portées', () => {
    const keys = allowedAppKeys(['crm_voir', 'app_crm_voir', 'app_gestion_projet_voir'])
    expect([...keys].sort()).toEqual(['crm', 'gestion_projet'])
  })
})

describe('buildInstalledApps (ODY26) — un rôle privé d’une app ne la voit plus', () => {
  const base = { disabledModules: [], role: 'admin' }

  it('sans marqueur, la visibilité historique est préservée à l’identique', () => {
    const apps = buildInstalledApps(makeConfigs(), { ...base, permissions: ['crm_voir'] })
    expect(apps.map((a) => a.key)).toEqual(['crm', 'ventes', 'admin-only-app'])
  })

  it('avec des marqueurs, seules les apps de la liste blanche restent', () => {
    const apps = buildInstalledApps(makeConfigs(), {
      ...base,
      permissions: ['crm_voir', appVisibilityPermission('crm'), appVisibilityPermission('ventes')],
    })
    expect(apps.map((a) => a.key)).toEqual(['crm', 'ventes'])
  })

  it('le marqueur ne RESSUSCITE jamais une app désactivée pour la société (ODX6 reste prioritaire)', () => {
    const apps = buildInstalledApps(makeConfigs(), {
      ...base,
      disabledModules: ['crm'],
      permissions: [appVisibilityPermission('crm'), appVisibilityPermission('ventes')],
    })
    expect(apps.map((a) => a.key)).toEqual(['ventes'])
  })

  it('le marqueur ne CONTOURNE jamais le gating de rôle (ARC47 reste prioritaire)', () => {
    const apps = buildInstalledApps(makeConfigs(), {
      disabledModules: [],
      role: 'normal',
      permissions: [appVisibilityPermission('admin-only-app'), appVisibilityPermission('crm')],
    })
    expect(apps.map((a) => a.key)).toEqual(['crm'])
  })
})

describe('useInstalledApps (ODY26) — câblage Redux de la liste blanche', () => {
  it('un rôle restreint à CRM ne voit plus l’app admin-only', () => {
    const { result } = renderInstalledApps({
      role: 'admin', permissions: [appVisibilityPermission('crm')],
    })
    expect(result.current.map((a) => a.key)).toEqual(['crm'])
  })
})
