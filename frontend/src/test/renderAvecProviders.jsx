import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../design/ThemeProvider.jsx'

/* Rendu PARTAGÉ des suites de pages : routeur mémoire + thème, rien d'autre. */
export function withProviders(ui) {
  return render(
    <MemoryRouter>
      <ThemeProvider>{ui}</ThemeProvider>
    </MemoryRouter>,
  )
}
