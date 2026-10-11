/* Harnais partagé des tests de pages Paramètres simples (ENF19). */
import { beforeAll } from 'vitest'
import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/** Polyfill ResizeObserver (jsdom) posé une fois avant les tests du fichier. */
export function declarerResizeObserver() {
  beforeAll(() => {
    if (typeof globalThis.ResizeObserver === 'undefined') {
      globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
    }
  })
}

export function renderPage(ui) {
  return render(<MemoryRouter><ThemeProvider>{ui}</ThemeProvider></MemoryRouter>)
}
