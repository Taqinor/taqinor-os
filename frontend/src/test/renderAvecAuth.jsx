import { render } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../design/ThemeProvider.jsx'

/* Rendu COMMUN des tests d'écran qui n'ont besoin que de `state.auth` (ENF19) :
   store Redux minimal `{ auth }`, routeur mémoire (`routeur`) et fournisseur de
   thème (`theme`) autour de l'élément. */
export function renderAvecAuth(ui, authState, { routeur = true, theme = false } = {}) {
  const store = configureStore({ reducer: { auth: (state = authState) => state } })
  let contenu = theme ? <ThemeProvider>{ui}</ThemeProvider> : ui
  if (routeur) contenu = <MemoryRouter>{contenu}</MemoryRouter>
  return render(<Provider store={store}>{contenu}</Provider>)
}
