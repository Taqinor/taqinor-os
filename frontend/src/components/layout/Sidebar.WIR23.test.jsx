// WIR23 — trois écrans construits mais orphelins de menu : /ia/actions,
// /ventes/listes-prix et /ventes/devis/action-requise. On vérifie ici
// uniquement la PRÉSENCE des liens.
// ODY4 — ces liens ne vivent plus dans une pile globale identique partout : ils
// sont dans la coquille de LEUR app (Intelligence pour /ia/actions, Ventes pour
// les deux autres). Chaque cas est donc rendu depuis une route de son app.
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { configureStore } from '@reduxjs/toolkit'
import Sidebar from './Sidebar'

function makeStore({ role = 'admin', permissions = [], modulesDesactives = [] } = {}) {
  return configureStore({
    reducer: {
      auth: (s = { role, permissions, modulesDesactives, user: null }) => s,
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
// le nom accessible peut être la CLÉ quand le catalogue ne la couvre pas. On
// vérifie donc la PRÉSENCE des liens par leur `href` (l'intention documentée en
// tête de fichier), robuste au catalogue.
function linkHrefs() {
  return screen.getAllByRole('link').map((l) => l.getAttribute('href'))
}

// Liens de la NAV de l'app active uniquement (hors en-tête d'app et sortie ⊞).
function navHrefs(container) {
  return Array.from(container.querySelectorAll('.sidebar-nav a')).map((a) => a.getAttribute('href'))
}

describe('Sidebar — WIR23 : trois écrans orphelins désormais cliquables', () => {
  it('« Actions IA » pointe vers /ia/actions depuis la coquille Intelligence', () => {
    renderSidebar({ path: '/ia' })
    expect(linkHrefs()).toContain('/ia/actions')
  })

  it('« Action requise » (devis) pointe vers /ventes/devis/action-requise depuis la coquille Ventes', () => {
    renderSidebar({ path: '/ventes/devis' })
    expect(linkHrefs()).toContain('/ventes/devis/action-requise')
  })

  it('« Listes de prix » pointe vers /ventes/listes-prix depuis la coquille Ventes', () => {
    renderSidebar({ path: '/ventes/devis' })
    expect(linkHrefs()).toContain('/ventes/listes-prix')
  })

  it('un rôle normal voit Actions IA (coquille Intelligence)', () => {
    const { container } = renderSidebar({ path: '/ia', role: 'normal' })
    expect(navHrefs(container)).toContain('/ia/actions')
  })

  it('un rôle normal voit Listes de prix (lecture ouverte) mais PAS Action requise (responsable/admin)', () => {
    const { container } = renderSidebar({ path: '/ventes/devis', role: 'normal' })
    const hrefs = navHrefs(container)
    expect(hrefs).toContain('/ventes/listes-prix')
    expect(hrefs).not.toContain('/ventes/devis/action-requise')
  })
})
