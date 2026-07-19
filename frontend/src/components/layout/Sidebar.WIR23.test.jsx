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

// Les libellés passent par `tr(item.k, …)` → i18n : hors I18nProvider (ce test),
// le nom accessible est la CLÉ, pas le libellé traduit. On vérifie donc la
// PRÉSENCE des liens par leur `href` (l'intention documentée en tête de fichier),
// robuste au fait que le catalogue ne soit pas chargé ici.
function linkHrefs() {
  return screen.getAllByRole('link').map((l) => l.getAttribute('href'))
}

describe('Sidebar — WIR23 : trois écrans orphelins désormais cliquables', () => {
  it('« Actions IA » (section INTELLIGENCE) pointe vers /ia/actions', () => {
    renderSidebar()
    expect(linkHrefs()).toContain('/ia/actions')
  })

  it('« Action requise » (devis) pointe vers /ventes/devis/action-requise', () => {
    renderSidebar()
    expect(linkHrefs()).toContain('/ventes/devis/action-requise')
  })

  it('« Listes de prix » pointe vers /ventes/listes-prix', () => {
    renderSidebar()
    expect(linkHrefs()).toContain('/ventes/listes-prix')
  })

  it('un rôle normal voit Actions IA et Listes de prix (lecture ouverte), pas Action requise (responsable/admin)', () => {
    renderSidebar({ role: 'normal' })
    const hrefs = linkHrefs()
    expect(hrefs).toContain('/ia/actions')
    expect(hrefs).toContain('/ventes/listes-prix')
    expect(hrefs).not.toContain('/ventes/devis/action-requise')
  })
})
