import { render } from '@testing-library/react'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../design/ThemeProvider.jsx'

/* ACAL345 — rendu PARTAGÉ d'un écran de liste ventes (store minimal ventes +
   auth, routeur mémoire, thème), au lieu de recopier ce gabarit dans chaque
   golden. `Ecran` est passé par l'appelant (ses modules sont mockés chez lui). */
export function renderListeVentes(Ecran, { devis, auth, route = '/ventes/devis' }) {
  const store = configureStore({
    reducer: {
      ventes: (s = { devis, loading: false, error: null }) => s,
      auth: (s = auth) => s,
    },
  })
  return render(
    <Provider store={store}>
      <MemoryRouter initialEntries={[route]}>
        <ThemeProvider>
          <Ecran />
        </ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}
