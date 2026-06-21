// N163 — Tests axe ciblés sur la coquille (layout chrome) que cette lane possède.
// On reste FOCALISÉ : on rend des composants isolés (Breadcrumbs, BottomTabBar,
// Sidebar) plutôt que des pages entières bruyantes, pour des assertions stables
// et rapides. `vitest-axe` lance axe-core sur le DOM rendu et échoue sur toute
// violation d'accessibilité (rôles, contrastes structurels, attributs ARIA…).
import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { configureStore } from '@reduxjs/toolkit'
import { axe } from 'vitest-axe'
import * as axeMatchers from 'vitest-axe/matchers'

import Breadcrumbs from '../components/layout/Breadcrumbs'
import BottomTabBar from '../components/layout/BottomTabBar'
import Sidebar from '../components/layout/Sidebar'

expect.extend(axeMatchers)

function authStore() {
  return configureStore({
    reducer: {
      auth: (s = { role: 'admin', permissions: [], user: null }) => s,
      parametres: (s = { profile: { nom: 'TAQINOR' } }) => s,
    },
  })
}

describe('a11y (N163) — coquille', () => {
  it('Breadcrumbs n’a aucune violation axe', async () => {
    const { container } = render(
      <MemoryRouter>
        <Breadcrumbs pathname="/ventes/devis" />
      </MemoryRouter>,
    )
    const results = await axe(container)
    expect(results).toHaveNoViolations()
  })

  it('Breadcrumbs tronqué (chemin long) n’a aucune violation axe', async () => {
    const crumbs = [
      { label: 'Niveau A', to: '/a' },
      { label: 'Niveau B', to: '/a/b' },
      { label: 'Niveau C', to: '/a/b/c' },
      { label: 'Page', to: '/a/b/c/d', current: true },
    ]
    const { container } = render(
      <MemoryRouter>
        <Breadcrumbs crumbs={crumbs} />
      </MemoryRouter>,
    )
    const results = await axe(container)
    expect(results).toHaveNoViolations()
  })

  it('BottomTabBar n’a aucune violation axe', async () => {
    const { container } = render(
      <MemoryRouter initialEntries={['/dashboard']}>
        <BottomTabBar onMore={() => {}} />
      </MemoryRouter>,
    )
    const results = await axe(container)
    expect(results).toHaveNoViolations()
  })

  it('Sidebar n’a aucune violation axe', async () => {
    const { container } = render(
      <Provider store={authStore()}>
        <MemoryRouter initialEntries={['/dashboard']}>
          <Sidebar collapsed={false} onToggle={() => {}} onNavigate={() => {}} />
        </MemoryRouter>
      </Provider>,
    )
    const results = await axe(container)
    expect(results).toHaveNoViolations()
  })
})
