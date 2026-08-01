import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'
import PinnedApps from './PinnedApps'

const PINNED_KEY = 'taqinor.sidebar.pinned'

// ODY1 — PinnedApps consomme désormais `useInstalledApps()` (registre ∩
// modules actifs ∩ rôle), donc `useSelector` a besoin d'un Provider — store
// minimal, même patron que BottomTabBar.test.jsx/Sidebar.test.jsx. Rôle admin
// par défaut (comportement historique du test : voit tous les modules).
function makeStore({ role = 'admin', permissions = [], modulesDesactives = [] } = {}) {
  return configureStore({
    reducer: { auth: (s = { role, permissions, modulesDesactives, user: null }) => s },
  })
}

function renderPinned(collapsed = false, storeOpts) {
  return render(
    <Provider store={makeStore(storeOpts)}>
      <MemoryRouter>
        <PinnedApps collapsed={collapsed} />
      </MemoryRouter>
    </Provider>,
  )
}

describe('VX10 — PinnedApps', () => {
  beforeEach(() => {
    window.localStorage.removeItem(PINNED_KEY)
  })

  it('rend rien (collapsed) même si des apps sont épinglées', () => {
    window.localStorage.setItem(PINNED_KEY, JSON.stringify(['compta']))
    const { container } = renderPinned(true)
    expect(container.firstChild).toBeNull()
  })

  it('affiche le bouton « épingler » quand rien n’est épinglé', () => {
    renderPinned(false)
    expect(screen.getByRole('button', { name: /Épingler une application/ })).toBeInTheDocument()
  })

  it('ouvre le sélecteur et épingle une app, persistée en localStorage', () => {
    renderPinned(false)
    fireEvent.click(screen.getByRole('button', { name: /Épingler une application/ }))
    const items = screen.getAllByRole('menuitemcheckbox')
    expect(items.length).toBeGreaterThan(0)
    fireEvent.click(items[0])
    const stored = JSON.parse(window.localStorage.getItem(PINNED_KEY) || '[]')
    expect(stored.length).toBe(1)
  })

  it('désépingler retire l’app de la bande et de localStorage', () => {
    // Épingle d'abord le premier module dispo pour connaître sa clé.
    renderPinned(false)
    fireEvent.click(screen.getByRole('button', { name: /Épingler une application/ }))
    const items = screen.getAllByRole('menuitemcheckbox')
    fireEvent.click(items[0])
    // Le même item est maintenant coché → un second clic désépingle.
    fireEvent.click(screen.getAllByRole('menuitemcheckbox')[0])
    const stored = JSON.parse(window.localStorage.getItem(PINNED_KEY) || '[]')
    expect(stored.length).toBe(0)
  })

  // ODY1 — source unique « mes apps » : une app désactivée (Paramètres →
  // Applications, ODX6) ou hors rôle disparaît de la bande ET du sélecteur.
  describe('ODY1 — module désactivé / rôle insuffisant', () => {
    it('une app épinglée devenue désactivée (ODX6) disparaît de la bande', () => {
      window.localStorage.setItem(PINNED_KEY, JSON.stringify(['crm']))
      renderPinned(false, { role: 'admin', modulesDesactives: ['crm'] })
      // Plus aucune app épinglée visible → repli « bouton épingler ».
      expect(screen.getByRole('button', { name: /Épingler une application/ })).toBeInTheDocument()
      expect(screen.queryByRole('link', { name: 'CRM' })).not.toBeInTheDocument()
    })

    it('le sélecteur ne propose pas une app désactivée (ODX6)', () => {
      renderPinned(false, { role: 'admin', modulesDesactives: ['crm'] })
      fireEvent.click(screen.getByRole('button', { name: /Épingler une application/ }))
      expect(screen.queryByRole('menuitemcheckbox', { name: 'CRM' })).not.toBeInTheDocument()
    })

    it('un rôle sans accès à AUCUNE app ne peut rien épingler (le sélecteur est vide)', () => {
      window.localStorage.setItem(PINNED_KEY, JSON.stringify(['crm']))
      renderPinned(false, { role: 'role-inexistant' })
      // Rôle hors de TOUTES les listes `roles` du registre → bande vide.
      expect(screen.getByRole('button', { name: /Épingler une application/ })).toBeInTheDocument()
      fireEvent.click(screen.getByRole('button', { name: /Épingler une application/ }))
      expect(screen.queryAllByRole('menuitemcheckbox').length).toBe(0)
    })
  })
})
