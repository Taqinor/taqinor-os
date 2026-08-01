// ODY8 — Matrice « module OFF × rôle » de l'écran « App non activée ».
//   • l'app est NOMMÉE (le registre la connaît même désactivée) ;
//   • CTA « Activer » visible pour un ADMIN seulement — les autres lisent
//     « demandez à votre administrateur » (jamais un bouton vers un 403) ;
//   • le lien Menu d'accueil est toujours là ;
//   • une clé inconnue ne fait pas planter l'écran.
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'

vi.mock('../../router/moduleRoutes', () => ({
  moduleConfigs: [
    {
      key: 'rh',
      nav: {
        label: 'Ressources humaines',
        items: [{ to: '/rh', label: 'Employés', icon: null, roles: ['admin'] }],
      },
    },
  ],
}))

import AppNotInstalled from './AppNotInstalled'

function renderEcran({ role = 'admin', app = 'rh' } = {}) {
  const store = configureStore({
    reducer: { auth: (s = { role, permissions: [], modulesDesactives: [], user: null }) => s },
  })
  return render(
    <Provider store={store}>
      <MemoryRouter initialEntries={[`/app-non-activee?app=${app}`]}>
        <AppNotInstalled />
      </MemoryRouter>
    </Provider>,
  )
}

describe('ODY8 — écran « App non activée »', () => {
  it('nomme l’app et explique le refus (admin)', () => {
    renderEcran({ role: 'admin' })
    expect(screen.getByRole('heading', { name: /Ressources humaines/ })).toBeInTheDocument()
    expect(screen.getByText(/n’est pas activée pour votre société/)).toBeInTheDocument()
  })

  it('admin : le CTA « Activer » pointe vers les Paramètres (ODX5)', () => {
    renderEcran({ role: 'admin' })
    const cta = screen.getByRole('link', { name: 'Activer' })
    expect(cta).toHaveAttribute('href', '/parametres')
  })

  it('non-admin : aucun CTA « Activer », un renvoi vers l’administrateur', () => {
    renderEcran({ role: 'normal' })
    expect(screen.queryByRole('link', { name: 'Activer' })).not.toBeInTheDocument()
    expect(screen.getByText(/Demandez à votre administrateur/)).toBeInTheDocument()
  })

  it('responsable : pas plus de CTA « Activer » qu’un rôle normal', () => {
    renderEcran({ role: 'responsable' })
    expect(screen.queryByRole('link', { name: 'Activer' })).not.toBeInTheDocument()
  })

  it('le lien Menu d’accueil est toujours présent, quel que soit le rôle', () => {
    renderEcran({ role: 'normal' })
    expect(screen.getByRole('link', { name: /Menu d’accueil/ })).toHaveAttribute('href', '/apps')
  })

  it('clé de module inconnue : message générique, aucun plantage', () => {
    renderEcran({ role: 'normal', app: 'module-fantome' })
    expect(screen.getByRole('heading', { name: /Cette application/ })).toBeInTheDocument()
  })
})
