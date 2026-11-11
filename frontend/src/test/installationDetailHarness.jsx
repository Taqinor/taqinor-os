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

// ADRG21 — l'administrateur livré porte les codes de la grille du chantier.
const AUTH_ADMIN = { role: 'admin', permissions: ['installation_gerer', 'intervention_gerer', 'equipement_gerer'] }

export function renderInstallationDetail(installation, auth = AUTH_ADMIN) {
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
