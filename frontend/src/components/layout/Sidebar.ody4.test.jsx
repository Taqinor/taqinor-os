// ODY4 — LA garde du paradigme : en immersion dans une app, AUCUNE entrée
// appartenant à une AUTRE app n'est visible dans la coquille.
// ----------------------------------------------------------------------------
// Le test ne compare pas à une liste écrite à la main (qui périmerait au
// premier module ajouté) : il RECONSTRUIT l'ensemble autorisé depuis le
// registre `moduleConfigs` via `appNavItems` — exactement la source que la
// Sidebar consomme. Toute destination rendue hors de cet ensemble (donc toute
// fuite d'une autre app) fait échouer le test en NOMMANT le lien fautif.
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { configureStore } from '@reduxjs/toolkit'
import Sidebar from './Sidebar'
import { moduleConfigs } from '../../router/moduleRoutes'
import { appNavItems, HOME_MENU_PATH } from '../../lib/apps/ActiveAppContext'

function makeStore({ role = 'admin', permissions = [], modulesDesactives = [] } = {}) {
  return configureStore({
    reducer: {
      auth: (s = { role, permissions, modulesDesactives, user: null }) => s,
      parametres: (s = { profile: { nom: 'TAQINOR' } }) => s,
    },
  })
}

function renderSidebar(path, opts = {}) {
  return render(
    <Provider store={makeStore(opts)}>
      <MemoryRouter initialEntries={[path]}>
        <Sidebar collapsed={false} onToggle={() => {}} onNavigate={() => {}} />
      </MemoryRouter>
    </Provider>,
  )
}

function allowedHrefs(appKey, role = 'admin', permissions = []) {
  const config = moduleConfigs.find((c) => c.key === appKey)
  const items = appNavItems(config, role, permissions).map((it) => it.to)
  // + le cockpit (en-tête d'app, = 1er item autorisé) + la sortie ⊞.
  return new Set([...items, HOME_MENU_PATH])
}

// Quatre apps représentatives, chacune ouverte sur un écran RÉEL de son app.
const CASES = [
  { key: 'crm', path: '/crm/leads', name: 'CRM' },
  { key: 'ventes', path: '/ventes/devis', name: 'VENTES' },
  { key: 'stock', path: '/stock/mouvements', name: 'STOCK' },
  { key: 'sav', path: '/sav', name: null },
]

describe('ODY4 — immersion : aucune entrée d’une AUTRE app dans la coquille', () => {
  CASES.forEach(({ key, path, name }) => {
    it(`en immersion « ${key} » (${path}), tout lien de la coquille appartient à cette app`, () => {
      const { container } = renderSidebar(path)
      const allowed = allowedHrefs(key)
      const aside = container.querySelector('aside.sidebar')
      expect(aside).toBeTruthy()
      const rendered = Array.from(aside.querySelectorAll('a[href]')).map((a) => a.getAttribute('href'))
      expect(rendered.length).toBeGreaterThan(0)
      const foreign = rendered.filter((href) => !allowed.has(href))
      // Message d'échec qui NOMME la fuite (jamais un « false » opaque).
      expect(foreign, `liens étrangers à l'app « ${key} » : ${foreign.join(', ')}`).toEqual([])
      if (name) expect(aside.querySelector('.sidebar-app-name').textContent).toBe(name)
    })
  })

  it('en immersion CRM, aucune destination Ventes / Stock / SAV / Paramètres n’est atteignable', () => {
    const { container } = renderSidebar('/crm/leads')
    const hrefs = Array.from(container.querySelectorAll('aside.sidebar a[href]'))
      .map((a) => a.getAttribute('href'))
    const forbiddenPrefixes = ['/ventes', '/stock', '/sav', '/parametres', '/admin', '/ged', '/ia', '/chantiers', '/reporting']
    forbiddenPrefixes.forEach((prefix) => {
      expect(hrefs.filter((h) => h === prefix || h.startsWith(`${prefix}/`))).toEqual([])
    })
    // …mais la nav CRM elle-même est bien là, intacte.
    expect(hrefs).toContain('/crm/leads')
    expect(hrefs).toContain('/activites') // VX83 « Ma file », rattachée à CRM
  })

  it('changer d’app change la coquille ENTIÈREMENT (rien ne survit de l’app précédente)', () => {
    const { container: crm } = renderSidebar('/crm/leads')
    const crmHrefs = Array.from(crm.querySelectorAll('.sidebar-nav a')).map((a) => a.getAttribute('href'))

    const { container: ventes } = renderSidebar('/ventes/devis')
    const ventesHrefs = Array.from(ventes.querySelectorAll('.sidebar-nav a')).map((a) => a.getAttribute('href'))

    expect(crmHrefs.some((h) => ventesHrefs.includes(h))).toBe(false)
  })

  it('la sortie ⊞ « Toutes les apps » est présente dans CHAQUE app', () => {
    CASES.forEach(({ path }) => {
      const { unmount } = renderSidebar(path)
      expect(screen.getByRole('link', { name: 'Toutes les apps' })).toHaveAttribute('href', HOME_MENU_PATH)
      unmount()
    })
  })
})
