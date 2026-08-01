// VX9/ODY1 — Tests du lanceur d'applications.
//   • Constat vérifié qui a motivé ODY1 : AVANT ce correctif, `AppLauncher`
//     lisait `moduleConfigs` directement (AppLauncher.jsx:14-16, historique) —
//     une app désactivée par Paramètres OU hors rôle restait visible. On
//     vérifie ici que le câblage sur `useInstalledApps()` corrige les DEUX.
import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, act } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'
import AppLauncher from './AppLauncher'

const PINNED_KEY = 'taqinor.sidebar.pinned'
const RECENT_KEY = 'taqinor.launcher.recent'

function makeStore({ role = 'admin', permissions = [], modulesDesactives = [] } = {}) {
  return configureStore({
    reducer: { auth: (s = { role, permissions, modulesDesactives, user: null }) => s },
  })
}

function renderLauncherOpen(storeOpts) {
  const utils = render(
    <Provider store={makeStore(storeOpts)}>
      <MemoryRouter>
        <AppLauncher />
      </MemoryRouter>
    </Provider>,
  )
  // Même déclencheur que le bouton grille du Header (event window), cf.
  // CommandPalette.quickcreate.test.jsx pour le même patron.
  act(() => { window.dispatchEvent(new Event('taqinor:app-launcher')) })
  return utils
}

describe('VX9 — AppLauncher', () => {
  beforeEach(() => {
    window.localStorage.removeItem(PINNED_KEY)
    window.localStorage.removeItem(RECENT_KEY)
  })

  it("s'ouvre sur l'événement `taqinor:app-launcher` et liste des apps", () => {
    renderLauncherOpen()
    expect(screen.getByRole('dialog', { name: /Lanceur d'applications/i })).toBeInTheDocument()
    expect(screen.getByText('Toutes les applications')).toBeInTheDocument()
    expect(screen.getAllByRole('listitem').length).toBeGreaterThan(0)
  })
})

// ODY1 — la grille = registre ∩ modules actifs (ODX6) ∩ rôle (ARC47), zéro
// autre source de liste d'apps.
describe('ODY1 — AppLauncher consomme useInstalledApps()', () => {
  beforeEach(() => {
    window.localStorage.removeItem(PINNED_KEY)
    window.localStorage.removeItem(RECENT_KEY)
  })

  it('une app désactivée pour la société (ODX6) disparaît du lanceur', () => {
    renderLauncherOpen({ modulesDesactives: ['crm'] })
    expect(screen.queryByText('CRM')).not.toBeInTheDocument()
  })

  it('une app active (non désactivée) reste visible', () => {
    renderLauncherOpen({ modulesDesactives: ['un-module-qui-n-existe-pas'] })
    expect(screen.getByText('CRM')).toBeInTheDocument()
  })

  it('un rôle sans accès à AUCUNE app rend le lanceur vide (pas de crash, pas de tuile orpheline)', () => {
    renderLauncherOpen({ role: 'role-inexistant' })
    expect(screen.queryAllByRole('listitem').length).toBe(0)
  })
})
