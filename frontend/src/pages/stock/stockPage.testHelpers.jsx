/* Harnais partagé des tests de pages Stock (ENF19) : store d'auth + rendu. */
import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import authReducer from '../../features/auth/store/authSlice'

export function makeAuthStore({
  role = 'admin', permissions = ['stock_modifier', 'stock_voir'], reducers = {},
} = {}) {
  return configureStore({
    reducer: { auth: authReducer, ...reducers },
    preloadedState: {
      auth: {
        user: { id: 1 }, role, role_nom: role, permissions,
        isAuthenticated: true, loading: false,
      },
    },
  })
}

export function renderStockPage(Page, store = makeAuthStore()) {
  return render(
    <Provider store={store}>
      <MemoryRouter>
        <ThemeProvider><Page /></ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}
