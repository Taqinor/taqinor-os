// ODY6 — la barre d'onglets basse EST celle de l'app active.
// ----------------------------------------------------------------------------
// Ces tests remplacent la matrice VX12 (« le tiroir Plus montre les catégories
// de PLUSIEURS apps ensemble »), qui décrivait exactement le comportement que
// le paradigme ERP-Apps retire : sous le pouce comme sur le bureau, on est
// DANS une app, et rien d'une autre app n'est visible. Ce qui reste vrai de
// M156 (plafond de 5 onglets, libellé textuel, aria-current) est conservé.
//
// Comme `Sidebar.ody4.test.jsx`, l'ensemble autorisé n'est jamais écrit à la
// main : il est reconstruit depuis `moduleConfigs` via `appNavItems` — la
// source que la coquille consomme réellement.
import { describe, it, expect } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'
import BottomTabBar, { splitAppTabs } from './BottomTabBar'
import { moduleConfigs } from '../../router/moduleRoutes'
import { appNavItems, HOME_MENU_PATH } from '../../lib/apps/ActiveAppContext'

// Store minimal, comme Sidebar.ody4.test.jsx : `modulesDesactives` est LU par
// `useInstalledApps` (ODX6) — l'omettre ferait retomber le sélecteur sur [],
// mais on l'écrit pour que l'intention du test soit explicite.
function makeStore({ role = 'admin', permissions = [], modulesDesactives = [] } = {}) {
  return configureStore({
    reducer: {
      auth: (s = { role, permissions, modulesDesactives, user: null }) => s,
    },
  })
}

function renderBar(path = '/ventes/devis', opts = {}) {
  return render(
    <Provider store={makeStore(opts)}>
      <MemoryRouter initialEntries={[path]}>
        <BottomTabBar />
      </MemoryRouter>
    </Provider>,
  )
}

function itemsOf(appKey, role = 'admin', permissions = []) {
  return appNavItems(moduleConfigs.find((c) => c.key === appKey), role, permissions)
}

describe('ODY6 — répartition des onglets (fonction pure)', () => {
  it('≤ 4 sections : toutes directes, aucun « Plus » (rien à cacher)', () => {
    const items = [{ to: '/a' }, { to: '/b' }, { to: '/c' }, { to: '/d' }]
    expect(splitAppTabs(items)).toEqual({ directs: items, more: false })
  })

  it('> 4 sections : 3 directes + « Plus » (l’onglet Apps occupe le 5e créneau)', () => {
    const items = [{ to: '/a' }, { to: '/b' }, { to: '/c' }, { to: '/d' }, { to: '/e' }]
    const { directs, more } = splitAppTabs(items)
    expect(directs).toHaveLength(3)
    expect(more).toBe(true)
  })

  it('aucune section : aucun onglet direct, aucun « Plus »', () => {
    expect(splitAppTabs([])).toEqual({ directs: [], more: false })
    expect(splitAppTabs(undefined)).toEqual({ directs: [], more: false })
  })
})

describe('ODY6 — la barre est celle de l’app active (M156 préservé)', () => {
  it('plafonne à 5 onglets maximum, onglet « Apps » compris', () => {
    // VENTES a 10 sections : c'est le cas où le plafond mord vraiment.
    const { container } = renderBar('/ventes/devis')
    expect(container.querySelectorAll('.bottom-tab').length).toBeLessThanOrEqual(5)
  })

  it('chaque onglet a un libellé textuel (pas seulement une icône)', () => {
    const { container } = renderBar('/ventes/devis')
    const tabs = container.querySelectorAll('.bottom-tab')
    expect(tabs.length).toBeGreaterThan(0)
    tabs.forEach((t) => {
      expect(t.querySelector('.bottom-tab-label')).toBeInTheDocument()
    })
  })

  it('l’onglet actif porte aria-current="page"', () => {
    const { container } = renderBar('/ventes/devis')
    const active = container.querySelector('.bottom-tab.active')
    expect(active).toBeInTheDocument()
    expect(active).toHaveAttribute('aria-current', 'page')
  })

  it('la barre s’annonce au nom de l’app et porte sa clé', () => {
    const { container } = renderBar('/ventes/devis')
    const nav = container.querySelector('nav.bottom-tabbar')
    expect(nav).toHaveAttribute('aria-label', 'Navigation VENTES')
    expect(nav).toHaveAttribute('data-app', 'ventes')
  })
})

describe('ODY6 — AUCUNE destination d’une autre app sous le pouce', () => {
  // Trois apps ouvertes chacune sur un écran RÉEL, comme Sidebar.ody4.test.jsx.
  const CASES = [
    { key: 'crm', path: '/crm/leads' },
    { key: 'ventes', path: '/ventes/devis' },
    { key: 'installations', path: '/chantiers' },
  ]

  CASES.forEach(({ key, path }) => {
    it(`en immersion « ${key} » (${path}), tout lien de la barre appartient à cette app`, () => {
      const { container } = renderBar(path)
      // Le Menu d'accueil est la SEULE affordance inter-apps tolérée : c'est la
      // sortie, pas une destination d'une autre app.
      const autorises = new Set([...itemsOf(key).map((it) => it.to), HOME_MENU_PATH])
      const rendus = Array.from(container.querySelectorAll('nav.bottom-tabbar a[href]'))
        .map((a) => a.getAttribute('href'))
      expect(rendus.length).toBeGreaterThan(0)
      rendus.forEach((href) => {
        expect(autorises.has(href), `fuite d’une autre app sous le pouce : ${href}`).toBe(true)
      })
    })
  })

  it('l’onglet « Apps » remplace l’ancien « Accueil » figé sur /dashboard', () => {
    const { container } = renderBar('/ventes/devis')
    const apps = container.querySelector('.bottom-tab-apps')
    expect(apps).toHaveAttribute('href', HOME_MENU_PATH)
    expect(within(apps).getByText('Apps')).toBeInTheDocument()
    // Plus aucun raccourci codé en dur vers une AUTRE app.
    expect(container.querySelector('nav.bottom-tabbar a[href="/dashboard"]')).toBeNull()
  })

  it('le nom accessible de l’onglet de sortie n’entre pas en collision avec le ⊞', () => {
    // Le ⊞ de l'en-tête et le pied de la Sidebar s'appellent « Toutes les
    // apps » ; l'onglet mobile s'appelle « Apps ». Deux cibles homonymes
    // feraient échouer les specs Playwright en mode strict.
    renderBar('/ventes/devis')
    expect(screen.queryByRole('link', { name: 'Toutes les apps' })).toBeNull()
    expect(screen.getByRole('link', { name: 'Apps' })).toBeInTheDocument()
  })
})

describe('ODY6 — le tiroir « Plus » est celui DE L’APP', () => {
  it('n’existe que si l’app a plus de sections que de créneaux', () => {
    // TABLEAU DE BORD (clé `admin`) n'a qu'une section : rien à replier.
    const { container } = renderBar('/dashboard')
    expect(container.querySelector('.bottom-tab-more')).toBeNull()
    expect(container.querySelectorAll('.bottom-tab')).toHaveLength(2) // Apps + Tableau de bord
  })

  it('ouvre la liste COMPLÈTE des sections de l’app, et d’aucune autre', async () => {
    renderBar('/ventes/devis')
    await userEvent.click(screen.getByRole('button', { name: /Plus de sections de VENTES/i }))
    const dialog = screen.getByRole('dialog', { name: /Sections de VENTES/i })
    const autorises = new Set(itemsOf('ventes').map((it) => it.to))
    const rendus = Array.from(dialog.querySelectorAll('a[href]')).map((a) => a.getAttribute('href'))
    expect(rendus).toHaveLength(autorises.size)
    rendus.forEach((href) => {
      expect(autorises.has(href), `fuite d’une autre app dans le tiroir : ${href}`).toBe(true)
    })
  })

  it('ne montre plus la grille de catégories inter-apps (acquis VX12 retiré)', async () => {
    renderBar('/ventes/devis')
    await userEvent.click(screen.getByRole('button', { name: /Plus de sections de VENTES/i }))
    expect(screen.queryByText('STOCK')).toBeNull()
    expect(screen.queryByRole('dialog', { name: /Toutes les applications/i })).toBeNull()
  })

  it('fermer le tiroir le retire du DOM', async () => {
    renderBar('/ventes/devis')
    await userEvent.click(screen.getByRole('button', { name: /Plus de sections de VENTES/i }))
    await userEvent.click(screen.getByRole('button', { name: /^Fermer$/ }))
    expect(screen.queryByRole('dialog', { name: /Sections de VENTES/i })).toBeNull()
  })
})

describe('ODY6 — hors de toute app, aucune barre', () => {
  it('sur le Menu d’accueil, la barre ne se rend pas (le menu EST l’accueil)', () => {
    const { container } = renderBar(HOME_MENU_PATH)
    expect(container.querySelector('.bottom-tabbar')).toBeNull()
  })

  it('sur un écran transverse (403), pas de barre non plus', () => {
    // `/403` (ui/Forbidden.jsx, acquis VX131) n'est déclaré par AUCUN
    // `module.config.jsx` : coquille neutre, donc aucune nav d'app.
    const { container } = renderBar('/403')
    expect(container.querySelector('.bottom-tabbar')).toBeNull()
  })

  it('une app désactivée pour la société ne rend pas de barre (ODX6)', () => {
    const { container } = renderBar('/ventes/devis', { modulesDesactives: ['ventes'] })
    expect(container.querySelector('.bottom-tabbar')).toBeNull()
  })
})
