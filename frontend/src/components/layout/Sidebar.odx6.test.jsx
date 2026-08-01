import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { configureStore } from '@reduxjs/toolkit'
import Sidebar from './Sidebar'

// ODX6 — la coquille ne rend jamais un module DÉSACTIVÉ pour la société.
// Défaut (aucun toggle → modulesDesactives = []) ⇒ comportement inchangé.
// ODY4 — depuis la bascule « ERP-Apps », le gating ne masque plus une SECTION
// dans une pile globale : il décide si l'app est ouvrable du tout (sinon la
// coquille redevient NEUTRE, en miroir de la garde de route `moduleLoader`).
function makeStore({ role = 'admin', permissions = [], modulesDesactives = [] } = {}) {
  return configureStore({
    reducer: {
      auth: (s = { role, permissions, modulesDesactives, user: null }) => s,
      parametres: (s = { profile: { nom: 'TAQINOR' } }) => s,
    },
  })
}

function renderSidebar({ path = '/stock', ...opts } = {}) {
  return render(
    <Provider store={makeStore(opts)}>
      <MemoryRouter initialEntries={[path]}>
        <Sidebar collapsed={false} onToggle={() => {}} onNavigate={() => {}} />
      </MemoryRouter>
    </Provider>,
  )
}

const appName = (container) => container.querySelector('.sidebar-app-name')?.textContent ?? null
const navHrefs = (container) =>
  Array.from(container.querySelectorAll('.sidebar-nav a')).map((a) => a.getAttribute('href'))

describe('ODX6 — coquille d’app filtrée par modules actifs', () => {
  it('défaut (aucun module désactivé) : entrer dans STOCK rend la coquille STOCK', () => {
    const { container } = renderSidebar({ path: '/stock' })
    expect(appName(container)).toBe('STOCK')
    expect(navHrefs(container)).toContain('/stock')
  })

  it('module « stock » désactivé : sa coquille n’est plus rendue (coquille neutre)', () => {
    const { container } = renderSidebar({ path: '/stock', modulesDesactives: ['stock'] })
    expect(container.querySelector('.sidebar-app')).toBeNull()
    expect(navHrefs(container)).toHaveLength(0)
  })

  it('désactiver « stock » ne touche pas CRM', () => {
    const { container } = renderSidebar({ path: '/crm/leads', modulesDesactives: ['stock'] })
    expect(appName(container)).toBe('CRM')
    expect(navHrefs(container)).toContain('/crm/leads')
  })

  it('ré-activer (retirer de la liste) restaure la coquille de l’app', () => {
    const { container } = renderSidebar({ path: '/stock', modulesDesactives: [] })
    expect(appName(container)).toBe('STOCK')
  })

  it('les apps fondation (Tableau de bord, Paramètres) ne sont jamais masquées par un toggle métier', () => {
    const { container: dash } = renderSidebar({
      path: '/dashboard', modulesDesactives: ['stock', 'crm', 'ventes'],
    })
    expect(appName(dash)).toBe('TABLEAU DE BORD')
    // ODY4 — exactement UN lien vers /dashboard : le littéral codé en dur de la
    // Sidebar en produisait un SECOND depuis que `features/admin/module.config`
    // déclare le sien (doublon réel, désormais résorbé).
    expect(navHrefs(dash).filter((h) => h === '/dashboard')).toHaveLength(1)

    const { container: params } = renderSidebar({
      path: '/parametres', modulesDesactives: ['stock', 'crm', 'ventes'],
    })
    expect(appName(params)).toBe('PARAMÈTRES')
    expect(navHrefs(params).filter((h) => h === '/admin/users')).toHaveLength(1)
  })

  it('ODY4 — un seul lien /messages (la section « tête » en dur ne le duplique plus)', () => {
    const { container } = renderSidebar({ path: '/messages' })
    expect(screen.getAllByRole('link', { name: /^Messages$/ })).toHaveLength(1)
    expect(navHrefs(container).filter((h) => h === '/messages')).toHaveLength(1)
  })
})
