// WIR23 — trois écrans construits mais orphelins de menu : /ia/actions
// (Sidebar, section INTELLIGENCE), /ventes/listes-prix et
// /ventes/devis/action-requise (ventes/module.config.jsx nav.items, miroir de
// /sav/action-requise). On vérifie ici uniquement la PRÉSENCE des liens.
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { configureStore } from '@reduxjs/toolkit'
import Sidebar from './Sidebar'

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

describe('Sidebar — WIR23 : trois écrans orphelins désormais cliquables', () => {
  it('« Actions IA » apparaît dans la section INTELLIGENCE et pointe vers /ia/actions', () => {
    renderSidebar()
    const link = screen.getByRole('link', { name: /Actions IA/ })
    expect(link).toHaveAttribute('href', '/ia/actions')
  })

  it('« Action requise » (devis) pointe vers /ventes/devis/action-requise', () => {
    // Deux menus portent le libellé « Action requise » (SAV ZSAV6 + ce miroir
    // ventes QX29/QX30, même motif volontaire) : on distingue par href, jamais
    // par un nom ambigu.
    renderSidebar()
    const links = screen.getAllByRole('link', { name: /Action requise/ })
    const hrefs = links.map((l) => l.getAttribute('href'))
    expect(hrefs).toContain('/ventes/devis/action-requise')
  })

  it('« Listes de prix » pointe vers /ventes/listes-prix', () => {
    renderSidebar()
    const link = screen.getByRole('link', { name: /Listes de prix/ })
    expect(link).toHaveAttribute('href', '/ventes/listes-prix')
  })

  it('un rôle normal voit toujours Actions IA et Listes de prix (lecture ouverte), pas Action requise (responsable/admin)', () => {
    renderSidebar({ role: 'normal' })
    expect(screen.getByRole('link', { name: /Actions IA/ })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Listes de prix/ })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /Action requise/ })).not.toBeInTheDocument()
  })
})
