import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { configureStore } from '@reduxjs/toolkit'
import DevisList from './DevisList'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* Aides de test PARTAGÉES des écrans « liste des devis » : rendu dans un store
   minimal (ventes + auth Directeur) et ouverture du menu « Plus d'actions » d'une
   ligne. Les `vi.mock` restent dans chaque fichier de test (ils s'appliquent
   aussi à ce module). Un seul endroit — jamais recopié test par test. */

export function renderListAvecStore(store) {
  return render(
    <Provider store={store}>
      <MemoryRouter initialEntries={['/ventes/devis']}>
        <ThemeProvider>
          <DevisList />
        </ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

export function renderList(devis) {
  const store = configureStore({
    reducer: {
      ventes: (s = { devis, loading: false, error: null }) => s,
      auth: (s = { role: 'admin', role_nom: 'Directeur', permissions: [] }) => s,
    },
  })
  return renderListAvecStore(store)
}

export async function ouvrirMenu(reference) {
  const user = userEvent.setup()
  const row = screen.getByText(reference).closest('tr')
  await user.click(within(row).getByRole('button', { name: /Plus d'actions/ }))
  return user
}
