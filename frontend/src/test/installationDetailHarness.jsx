import { render } from '@testing-library/react'
import { Provider } from 'react-redux'
import { ConfirmProvider } from '../providers/ConfirmProvider'
import { MemoryRouter } from 'react-router-dom'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../design/ThemeProvider.jsx'
import InstallationDetail from '../pages/installations/InstallationDetail'

/* Harnais de rendu partagé des tests de la fiche chantier (CIQ637) : un seul
   endroit plutôt qu'une copie dans chaque fichier de test
   (check_duplicats_litteraux). */

export function renderInstallationDetail(installation, auth = { role: 'admin' }) {
  const store = configureStore({
    reducer: { auth: (state = auth) => state, stock: (state = { produits: [{ id: 1, nom: 'Panneau' }] }) => state },
  })
  return render(
    <Provider store={store}>
      <MemoryRouter initialEntries={['/chantiers']}>
        <ThemeProvider>
          <ConfirmProvider>
            <InstallationDetail installation={installation} onClose={() => {}} onSaved={() => {}} />
          </ConfirmProvider>
        </ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}
