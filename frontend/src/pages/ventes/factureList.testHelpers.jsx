/* Rendu partagé des tests FactureList (ENF19) : store ventes/auth minimal + routeur + thème. */
import { render } from '@testing-library/react'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

export function renderFactureList(FactureList, { factures = [], role = 'admin' } = {}) {
  const store = configureStore({
    reducer: {
      ventes: (s = { factures, loading: false, error: null }) => s,
      auth: (s = { role }) => s,
    },
  })
  return render(
    <Provider store={store}>
      <MemoryRouter initialEntries={['/ventes/factures']}>
        <ThemeProvider><FactureList /></ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}
