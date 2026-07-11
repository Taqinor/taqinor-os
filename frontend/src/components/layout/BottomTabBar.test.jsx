import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'
import BottomTabBar from './BottomTabBar'

// VX12 — le tiroir « Plus » lit role/permissions (mêmes règles de gating que
// la Sidebar) : store minimal, comme Sidebar.test.jsx.
function makeStore({ role = 'admin', permissions = [] } = {}) {
  return configureStore({
    reducer: {
      auth: (s = { role, permissions, user: null }) => s,
    },
  })
}

function renderBar(opts = {}) {
  return render(
    <Provider store={makeStore(opts)}>
      <MemoryRouter initialEntries={['/dashboard']}>
        <BottomTabBar />
      </MemoryRouter>
    </Provider>,
  )
}

describe('BottomTabBar — M156 polissage nav basse', () => {
  it('plafonne à 5 onglets maximum (≤ 4 liens + bouton « Plus »)', () => {
    const { container } = renderBar()
    const tabs = container.querySelectorAll('.bottom-tab')
    expect(tabs.length).toBeLessThanOrEqual(5)
  })

  it('l’onglet actif porte aria-current="page"', () => {
    const { container } = renderBar()
    const active = container.querySelector('.bottom-tab.active')
    expect(active).toBeInTheDocument()
    expect(active).toHaveAttribute('aria-current', 'page')
  })

  it('chaque onglet a un libellé textuel (pas seulement une icône)', () => {
    const { container } = renderBar()
    container.querySelectorAll('.bottom-tab').forEach((t) => {
      expect(t.querySelector('.bottom-tab-label')).toBeInTheDocument()
    })
  })
})

describe('VX12 — « Plus » ouvre la grille de modules (2 niveaux), pas le tiroir complet', () => {
  it('« Plus » affiche la GRILLE de catégories en premier (pas la liste plate des items)', async () => {
    renderBar()
    await userEvent.click(screen.getByRole('button', { name: /Plus de menus/i }))
    expect(screen.getByRole('dialog', { name: /Toutes les applications/i })).toBeInTheDocument()
    expect(screen.getByText('STOCK')).toBeInTheDocument()
    expect(screen.getByText('VENTES')).toBeInTheDocument()
  })

  it('taper une catégorie déroule ses items (2e niveau) avec un retour à la grille', async () => {
    renderBar()
    await userEvent.click(screen.getByRole('button', { name: /Plus de menus/i }))
    await userEvent.click(screen.getByText('VENTES'))
    // 2e niveau : les items de VENTES apparaissent (ex. Devis). Le libellé
    // « Devis » peut apparaître plus d'une fois (drawer + sous-menu) ; on
    // vérifie sa présence sans exiger l'unicité.
    expect(screen.getAllByRole('link', { name: /Devis/ }).length).toBeGreaterThan(0)
    // Bouton retour vers la grille.
    const back = screen.getByRole('button', { name: /Retour à la grille/i })
    await userEvent.click(back)
    expect(screen.getByText('STOCK')).toBeInTheDocument()
  })

  it('fermer le tiroir retire le dialog du DOM', async () => {
    renderBar()
    await userEvent.click(screen.getByRole('button', { name: /Plus de menus/i }))
    await userEvent.click(screen.getByRole('button', { name: /^Fermer$/ }))
    expect(screen.queryByRole('dialog', { name: /Toutes les applications/i })).not.toBeInTheDocument()
  })
})
