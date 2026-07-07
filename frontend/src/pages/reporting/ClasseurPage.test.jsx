import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
  }
})

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/reporting/classeurs/9']}>
      <ThemeProvider>
        <Routes>
          <Route path="/reporting/classeurs/:id" element={<ClasseurPage />} />
        </Routes>
      </ThemeProvider>
    </MemoryRouter>,
  )
}

/* XPLT22 — classeur léger embarqué (mini-spreadsheet BI, données live).
   Grille de cellules éditable, formules =SOMME(...), rafraîchissement live. */

vi.mock('../../api/reportingApi', () => ({
  default: {
    getClasseur: vi.fn(() => Promise.resolve({
      data: {
        id: 9, titre: 'Suivi CA', partage: false,
        cellules: { A1: { valeur: 10 }, A2: { formule: '=SOMME(A1:A1)' } },
        liens: {},
      },
    })),
    rafraichirClasseur: vi.fn(() => Promise.resolve({
      data: { cellules: { A1: 10, A2: 10 } },
    })),
    updateClasseur: vi.fn(() => Promise.resolve({ data: {} })),
  },
}))

import reportingApi from '../../api/reportingApi'
import ClasseurPage from './ClasseurPage'

describe('ClasseurPage (XPLT22 — mini-tableur BI)', () => {
  it('charge le classeur et affiche la grille avec les cellules existantes', async () => {
    renderPage()

    expect(await screen.findByText('Suivi CA')).toBeInTheDocument()
    expect(await screen.findByTestId('classeur-grid')).toBeInTheDocument()
    const cellA1 = screen.getByLabelText('Cellule A1')
    expect(cellA1).toHaveValue('10')
    const cellA2 = screen.getByLabelText('Cellule A2')
    expect(cellA2).toHaveValue('=SOMME(A1:A1)')

    await waitFor(() => expect(reportingApi.getClasseur).toHaveBeenCalledWith('9'))
  })

  it('rafraîchir appelle rafraichirClasseur', async () => {
    renderPage()
    await screen.findByText('Suivi CA')

    screen.getByTestId('classeur-rafraichir').click()
    await waitFor(() => expect(reportingApi.rafraichirClasseur).toHaveBeenCalledWith('9'))
  })

  it('enregistrer appelle updateClasseur avec les cellules courantes', async () => {
    renderPage()
    await screen.findByText('Suivi CA')

    screen.getByTestId('classeur-enregistrer').click()
    await waitFor(() => expect(reportingApi.updateClasseur).toHaveBeenCalledWith(
      '9', { cellules: { A1: { valeur: 10 }, A2: { formule: '=SOMME(A1:A1)' } } },
    ))
  })
})
