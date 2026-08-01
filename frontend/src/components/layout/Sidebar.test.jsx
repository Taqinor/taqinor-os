import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { configureStore } from '@reduxjs/toolkit'
import Sidebar from './Sidebar'

// Reducers minimaux pour alimenter les sélecteurs lus par la Sidebar.
function makeStore({ role = 'admin', permissions = [], modulesDesactives = [] } = {}) {
  return configureStore({
    reducer: {
      auth: (s = { role, permissions, modulesDesactives, user: null }) => s,
      parametres: (s = { profile: { nom: 'TAQINOR' } }) => s,
    },
  })
}

// ODY4 — la coquille est celle de l'APP ACTIVE, déduite de la route : chaque
// rendu part donc d'un chemin explicite (il n'existe plus de « pile globale »
// identique sur tous les écrans).
function renderSidebar({ path = '/stock', collapsed = false, ...opts } = {}) {
  return render(
    <Provider store={makeStore(opts)}>
      <MemoryRouter initialEntries={[path]}>
        <Sidebar collapsed={collapsed} onToggle={() => {}} onNavigate={() => {}} />
      </MemoryRouter>
    </Provider>,
  )
}

const navLinks = (container) => Array.from(container.querySelectorAll('.sidebar-nav a'))
const navHrefs = (container) => navLinks(container).map((a) => a.getAttribute('href'))

describe('Sidebar — I135 « calme » + P168 icônes (en immersion d’app)', () => {
  it('marque l’item actif avec aria-current="page" (et la classe active)', () => {
    renderSidebar({ path: '/stock' })
    // Un SEUL item de nav « Produits » (le doublon Sidebar-en-dur ↔ module.config
    // n'existe plus depuis ODY4) : la requête singulière est donc légitime.
    const active = screen.getByRole('link', { name: /^Produits$/ })
    expect(active).toHaveAttribute('aria-current', 'page')
    expect(active.className).toMatch(/\bactive\b/)
  })

  it('les items inactifs n’ont PAS aria-current', () => {
    renderSidebar({ path: '/stock' })
    const inactive = screen.getByRole('link', { name: /^Mouvements$/ })
    expect(inactive).not.toHaveAttribute('aria-current')
  })

  it('chaque destination de la nav n’apparaît QU’UNE fois (anti-doublon ODY4)', () => {
    const { container } = renderSidebar({ path: '/stock' })
    const hrefs = navHrefs(container)
    expect(hrefs.length).toBeGreaterThan(1)
    expect(new Set(hrefs).size).toBe(hrefs.length)
  })

  it('P168 — les icônes de nav sont des SVG lucide (classe lucide), pas des SVG inline ad hoc', () => {
    const { container } = renderSidebar({ path: '/stock' })
    const navIcons = container.querySelectorAll('.sidebar-nav-icon svg')
    expect(navIcons.length).toBeGreaterThan(0)
    // lucide-react ajoute une classe "lucide" sur chaque icône rendue.
    navIcons.forEach((svg) => {
      expect(svg.getAttribute('class') || '').toMatch(/lucide/)
    })
  })

  it('P168 — taille d’icône standardisée (width === height, valeur de l’échelle)', () => {
    const { container } = renderSidebar({ path: '/stock' })
    const svg = container.querySelector('.sidebar-nav-icon svg')
    expect(svg).toBeTruthy()
    const w = svg.getAttribute('width')
    const h = svg.getAttribute('height')
    expect(w).toBe(h)
  })
})

describe('Sidebar — VX8 : l’accent de l’app active habille la coquille', () => {
  it('STOCK porte l’accent « lune » sur sa section de nav', () => {
    const { container } = renderSidebar({ path: '/stock' })
    const section = container.querySelector('.sidebar-section')
    expect(section.style.getPropertyValue('--module-accent')).toBe('var(--module-accent-lune)')
  })

  it('VENTES garde le brass historique — un accent DISTINCT de celui de STOCK', () => {
    const { container: ventes } = renderSidebar({ path: '/ventes/devis' })
    const ventesAccent = ventes.querySelector('.sidebar-section').style.getPropertyValue('--module-accent')
    expect(ventesAccent).toBe('var(--module-accent-brass)')

    const { container: stock } = renderSidebar({ path: '/stock' })
    const stockAccent = stock.querySelector('.sidebar-section').style.getPropertyValue('--module-accent')
    expect(ventesAccent).not.toBe(stockAccent)
  })
})

describe('Sidebar — ODY4 : identité de l’app active + sortie ⊞', () => {
  it('affiche le nom de l’app active, et il CHANGE avec la route', () => {
    const { container: stock } = renderSidebar({ path: '/stock' })
    expect(stock.querySelector('.sidebar-app-name').textContent).toBe('STOCK')

    const { container: ventes } = renderSidebar({ path: '/ventes/devis' })
    expect(ventes.querySelector('.sidebar-app-name').textContent).toBe('VENTES')
  })

  it('l’en-tête d’app pointe vers le cockpit (1er écran autorisé) de l’app', () => {
    const { container } = renderSidebar({ path: '/ventes/factures' })
    expect(container.querySelector('.sidebar-app').getAttribute('href')).toBe('/ventes/cockpit')
  })

  it('un pied « Toutes les apps » ramène au Menu d’accueil', () => {
    renderSidebar({ path: '/stock' })
    const exit = screen.getByRole('link', { name: 'Toutes les apps' })
    expect(exit).toHaveAttribute('href', '/apps')
  })

  it('hors de toute app (Menu d’accueil), la coquille est NEUTRE : aucune nav d’app', () => {
    const { container } = renderSidebar({ path: '/apps' })
    expect(container.querySelector('.sidebar-app')).toBeNull()
    expect(navLinks(container)).toHaveLength(0)
    // La sortie reste offerte (on est déjà au Menu d'accueil, mais la coquille
    // ne se contredit jamais d'un écran à l'autre).
    expect(screen.getByRole('link', { name: 'Toutes les apps' })).toBeInTheDocument()
  })
})
