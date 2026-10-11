/* Harnais partagé des tests de pages GED avancées (ENF19). */
import { vi } from 'vitest'
import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { createElement } from 'react'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'

export const crmApiClientAlpha = () => ({
  default: {
    getClients: vi.fn(() => Promise.resolve({ data: [{ id: 5, nom: 'Client Alpha' }] })),
  },
})

/** Barrel `ui` réel, `toast` remplacé par des espions. */
export const uiToastEspion = (actual) => ({
  ...actual, toast: { success: vi.fn(), error: vi.fn(), message: vi.fn() },
})

export function renderGedPage(Page) {
  return render(<MemoryRouter><ThemeProvider>{createElement(Page)}</ThemeProvider></MemoryRouter>)
}
