// ODY9 — LE contrat « un composant, quatre surfaces ».
// La garde qui compte : pour la MÊME app, les surfaces qui listent des apps
// (Menu d'accueil, lanceur VX9, épinglés VX10, écran Applications ODX5)
// rendent le MÊME glyphe, celui du registre. On marque donc l'icône du
// registre d'un sentinel : si une surface repartait sur sa propre résolution
// (le défaut historique de l'écran Applications, qui lisait le manifest
// backend), le sentinel n'apparaîtrait pas.
import { describe, it, expect, vi } from 'vitest'
import { render, screen, act } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'

// Sentinel TEXTUEL (pas de JSX dans une factory vi.mock, qui est hoistée).
const SENTINEL = 'GLYPHE-CRM'

vi.mock('../router/moduleRoutes', () => ({
  moduleConfigs: [
    {
      key: 'crm',
      order: 10,
      nav: {
        label: 'CRM',
        accent: 'azur',
        items: [{ to: '/crm', label: 'Clients', icon: 'GLYPHE-CRM', roles: ['admin'] }],
      },
    },
  ],
}))

import AppIcon from './AppIcon'
import { iconNodeForApp, accentForApp } from '../lib/apps/appIcon'
import HomeMenu from '../pages/home/HomeMenu'
import PinnedApps from '../components/layout/PinnedApps'
import AppLauncher from '../components/layout/AppLauncher'

function makeStore() {
  return configureStore({
    reducer: { auth: (s = { role: 'admin', permissions: [], modulesDesactives: [], user: null }) => s },
  })
}

const enveloppe = (ui) => (
  <Provider store={makeStore()}><MemoryRouter>{ui}</MemoryRouter></Provider>
)

describe('ODY9 — AppIcon (pastille)', () => {
  it('rend le glyphe fourni dans un conteneur dimensionné par la taille demandée', () => {
    const { container } = render(<AppIcon icon={SENTINEL} accent="azur" size="lg" />)
    const pastille = container.querySelector('.app-icon')
    expect(pastille).toBeInTheDocument()
    expect(pastille.getAttribute('data-app-icon-size')).toBe('lg')
    expect(pastille.style.getPropertyValue('--app-icon-size')).toBe('64px')
    expect(screen.getByText(SENTINEL)).toBeInTheDocument()
  })

  it('porte l’accent de module VX8 en variable CSS (jamais une couleur en dur)', () => {
    const { container } = render(<AppIcon icon={SENTINEL} accent="azur" />)
    expect(container.querySelector('.app-icon').style.getPropertyValue('--module-accent'))
      .toBe('var(--module-accent-azur)')
  })

  it('sans accent, aucune variable posée : la pastille hérite du thème', () => {
    const { container } = render(<AppIcon icon={SENTINEL} />)
    expect(container.querySelector('.app-icon').style.getPropertyValue('--module-accent')).toBe('')
  })

  it('décorative par défaut (aria-hidden), nommée seulement si un label est donné', () => {
    const { container, rerender } = render(<AppIcon icon={SENTINEL} />)
    expect(container.querySelector('.app-icon')).toHaveAttribute('aria-hidden', 'true')
    rerender(<AppIcon icon={SENTINEL} label="CRM" />)
    expect(screen.getByRole('img', { name: 'CRM' })).toBeInTheDocument()
  })

  it('les tailles du contrat sont 64 / 56 / 48 px', () => {
    const attendu = { lg: '64px', md: '56px', sm: '48px' }
    Object.entries(attendu).forEach(([taille, px]) => {
      const { container, unmount } = render(<AppIcon icon={SENTINEL} size={taille} />)
      expect(container.querySelector('.app-icon').style.getPropertyValue('--app-icon-size')).toBe(px)
      unmount()
    })
  })
})

describe('ODY9 — le même glyphe sur toutes les surfaces', () => {
  it('lib/apps/appIcon résout l’icône ET l’accent depuis LE registre', () => {
    expect(iconNodeForApp('crm')).toBe(SENTINEL)
    expect(accentForApp('crm')).toBe('azur')
    // Module inconnu du registre (backend seul) : `null`, repli à l'appelant.
    expect(iconNodeForApp('module-backend-seul')).toBeNull()
  })

  it('Menu d’accueil : la tuile rend le glyphe du registre dans une .app-icon', () => {
    const { container } = render(enveloppe(<HomeMenu />))
    expect(container.querySelector('.app-icon')).toBeInTheDocument()
    expect(screen.getAllByText(SENTINEL).length).toBeGreaterThan(0)
  })

  it('Épinglés (VX10) : même pastille, même glyphe', () => {
    window.localStorage.setItem('taqinor.sidebar.pinned', JSON.stringify(['crm']))
    const { container } = render(enveloppe(<PinnedApps collapsed={false} />))
    expect(container.querySelector('.app-icon')).toBeInTheDocument()
    expect(screen.getAllByText(SENTINEL).length).toBeGreaterThan(0)
    window.localStorage.removeItem('taqinor.sidebar.pinned')
  })

  it('Lanceur (VX9) : même pastille, même glyphe, une fois ouvert', () => {
    render(enveloppe(<AppLauncher />))
    // Même déclencheur que le bouton grille du Header (cf. AppLauncher.test.jsx).
    act(() => { window.dispatchEvent(new Event('taqinor:app-launcher')) })
    // L'overlay Radix rend en portail : on cherche dans le document entier.
    expect(document.querySelectorAll('.app-icon').length).toBeGreaterThan(0)
    expect(screen.getAllByText(SENTINEL).length).toBeGreaterThan(0)
  })
})
