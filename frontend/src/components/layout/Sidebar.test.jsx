import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { configureStore } from '@reduxjs/toolkit'
import Sidebar from './Sidebar'

// Reducers minimaux pour alimenter les sélecteurs lus par la Sidebar.
function makeStore({ role = 'admin', permissions = [] } = {}) {
  return configureStore({
    reducer: {
      auth: (s = { role, permissions, user: null }) => s,
      parametres: (s = { profile: { nom: 'TAQINOR' } }) => s,
    },
  })
}

function renderSidebar({ path = '/dashboard', collapsed = false, ...opts } = {}) {
  return render(
    <Provider store={makeStore(opts)}>
      <MemoryRouter initialEntries={[path]}>
        <Sidebar collapsed={collapsed} onToggle={() => {}} onNavigate={() => {}} />
      </MemoryRouter>
    </Provider>,
  )
}

describe('Sidebar — I135 « calme » + P168 icônes', () => {
  it('marque l’item actif avec aria-current="page" (et la classe active)', () => {
    renderSidebar({ path: '/dashboard' })
    const active = screen.getByRole('link', { name: /Dashboard/ })
    expect(active).toHaveAttribute('aria-current', 'page')
    expect(active.className).toMatch(/\bactive\b/)
  })

  it('les items inactifs n’ont PAS aria-current', () => {
    renderSidebar({ path: '/dashboard' })
    const inactive = screen.getByRole('link', { name: /Messages/ })
    expect(inactive).not.toHaveAttribute('aria-current')
  })

  it('rend des séparateurs de section avec un libellé', () => {
    renderSidebar({ path: '/dashboard' })
    expect(screen.getByText('STOCK')).toBeInTheDocument()
    expect(screen.getByText('VENTES')).toBeInTheDocument()
  })

  it('P168 — les icônes de nav sont des SVG lucide (classe lucide), pas des SVG inline ad hoc', () => {
    const { container } = renderSidebar({ path: '/dashboard' })
    const navIcons = container.querySelectorAll('.sidebar-nav-icon svg')
    expect(navIcons.length).toBeGreaterThan(0)
    // lucide-react ajoute une classe "lucide" sur chaque icône rendue.
    navIcons.forEach((svg) => {
      expect(svg.getAttribute('class') || '').toMatch(/lucide/)
    })
  })

  it('P168 — taille d’icône standardisée (width === height, valeur de l’échelle)', () => {
    const { container } = renderSidebar({ path: '/dashboard' })
    const svg = container.querySelector('.sidebar-nav-icon svg')
    expect(svg).toBeTruthy()
    const w = svg.getAttribute('width')
    const h = svg.getAttribute('height')
    expect(w).toBe(h)
  })

  it('VX8 — chaque section de nav porte un accent de module perceptible et distinct', () => {
    const { container } = renderSidebar({ path: '/dashboard' })
    const sections = Array.from(container.querySelectorAll('.sidebar-section'))
    expect(sections.length).toBeGreaterThan(1)
    // La section STOCK (2e, sans label sur la 1re) déclare bien --module-accent.
    const stockSection = sections.find((s) => s.textContent.includes('STOCK'))
    expect(stockSection.style.getPropertyValue('--module-accent')).toBe('var(--module-accent-lune)')
    // VENTES garde le brass historique (règle explicite de la tâche).
    const ventesSection = sections.find((s) => s.textContent.includes('VENTES'))
    expect(ventesSection.style.getPropertyValue('--module-accent')).toBe('var(--module-accent-brass)')
    // Deux sections différentes déclarent des clés d'accent différentes.
    const crmSection = sections.find((s) => s.textContent.includes('CRM'))
    expect(crmSection.style.getPropertyValue('--module-accent')).not.toBe(
      stockSection.style.getPropertyValue('--module-accent'),
    )
  })
})
