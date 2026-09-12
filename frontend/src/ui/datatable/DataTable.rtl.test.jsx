import { describe, it, expect, beforeEach } from 'vitest'
import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import { setStoredDensity } from '../../design/theme.js'

import { DataTable } from './DataTable.jsx'

/* NTI18N2 — layout miroir RTL : la case-à-cocher (toujours première colonne)
   et la colonne Actions (toujours dernière) doivent s'ancrer via des
   propriétés LOGIQUES (`start-0`/`end-0`) plutôt que physiques
   (`left-0`/`right-0`), et les chevrons de pagination doivent porter la
   classe de miroir conditionnel `rtl:-scale-x-100` (appliquée par Tailwind
   UNIQUEMENT sous `[dir="rtl"]` — un rendu jsdom en LTR par défaut ne peut
   donc que vérifier la PRÉSENCE de ces classes, pas leur effet visuel réel,
   couvert par le spec Playwright `e2e/rtl-layout.spec.js`). */

function wrapper({ children }) {
  return (
    <MemoryRouter>
      <ThemeProvider>{children}</ThemeProvider>
    </MemoryRouter>
  )
}

const DATA = [
  { id: 1, nom: 'Kasri', ville: 'Rabat' },
  { id: 2, nom: 'Benani', ville: 'Casablanca' },
]
const COLUMNS = [
  { id: 'nom', header: 'Nom' },
  { id: 'ville', header: 'Ville' },
]

function renderTable(props = {}) {
  return render(
    <DataTable
      data={DATA} columns={COLUMNS} selectable
      rowActions={() => []}
      {...props}
    />,
    { wrapper },
  )
}

beforeEach(() => { setStoredDensity('comfortable') })

describe('NTI18N2 — DataTable, ancrage logique + chevrons miroir', () => {
  it('ancre la colonne case-à-cocher via `start-0` (jamais `left-0`)', () => {
    const { container } = renderTable()
    const checkboxCell = container.querySelector('th.sticky, td.sticky')
    // Au moins une cellule sticky de bord existe et aucune ne porte plus la
    // classe physique `left-0`/`right-0` retirée par cette tâche.
    expect(container.querySelector('.sticky.start-0, .sticky.end-0')).toBeTruthy()
    expect(container.querySelector('.sticky.left-0')).toBeFalsy()
    expect(container.querySelector('.sticky.right-0')).toBeFalsy()
    expect(checkboxCell).toBeTruthy()
  })

  it("l'en-tête par défaut (sans align explicite) utilise `text-start`, jamais `text-left`", () => {
    const { container } = renderTable()
    const header = [...container.querySelectorAll('th')]
      .find((th) => th.textContent.includes('Nom'))
    expect(header?.className).toContain('text-start')
    expect(header?.className).not.toContain('text-left')
  })

  it('les chevrons de pagination portent le miroir conditionnel rtl:', () => {
    // La pagination s'affiche dès que `rows.length > 0` (DATA en a 2) — pas
    // besoin d'un grand jeu de données pour faire apparaître les chevrons.
    const { container } = renderTable()
    const svgs = [...container.querySelectorAll('svg')]
      .filter((svg) => svg.getAttribute('class')?.includes('-scale-x-100'))
    expect(svgs.length).toBeGreaterThan(0)
  })
})
