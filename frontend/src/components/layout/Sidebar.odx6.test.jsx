import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { configureStore } from '@reduxjs/toolkit'
import Sidebar from './Sidebar'

// ODX6 — la nav masque les sections des modules DÉSACTIVÉS pour la société.
// Défaut (aucun toggle → modulesDesactives = []) ⇒ nav strictement identique.
function makeStore({ role = 'admin', permissions = [], modulesDesactives = [] } = {}) {
  return configureStore({
    reducer: {
      auth: (s = { role, permissions, modulesDesactives, user: null }) => s,
      parametres: (s = { profile: { nom: 'TAQINOR' } }) => s,
    },
  })
}

function renderSidebar(opts = {}) {
  return render(
    <Provider store={makeStore(opts)}>
      <MemoryRouter initialEntries={['/dashboard']}>
        <Sidebar collapsed={false} onToggle={() => {}} onNavigate={() => {}} />
      </MemoryRouter>
    </Provider>,
  )
}

describe('ODX6 — Sidebar filtrée par modules actifs', () => {
  it('défaut (aucun module désactivé) : STOCK et CRM visibles', () => {
    renderSidebar()
    expect(screen.getByText('STOCK')).toBeInTheDocument()
    expect(screen.getByText('CRM')).toBeInTheDocument()
  })

  it('module « stock » désactivé : la section STOCK disparaît, CRM reste', () => {
    renderSidebar({ modulesDesactives: ['stock'] })
    expect(screen.queryByText('STOCK')).not.toBeInTheDocument()
    expect(screen.getByText('CRM')).toBeInTheDocument()
  })

  it('ré-activer (retirer de la liste) restaure la section', () => {
    // Simule la restauration : liste vide ⇒ STOCK de retour.
    renderSidebar({ modulesDesactives: [] })
    expect(screen.getByText('STOCK')).toBeInTheDocument()
  })

  it('les surfaces globales (Dashboard, Administration) ne sont jamais masquées', () => {
    renderSidebar({ modulesDesactives: ['stock', 'crm', 'ventes'] })
    // Dashboard = section globale sans clé.
    expect(screen.getByRole('link', { name: /Dashboard/ })).toBeInTheDocument()
    // Administration = section globale sans clé.
    expect(screen.getByText('ADMINISTRATION')).toBeInTheDocument()
  })
})
