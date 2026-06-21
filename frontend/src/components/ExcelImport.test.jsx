import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'

/* P169 — ExcelImport : refonte sans style={} en dur (Tailwind/tokens). Test de
   non-régression : le modal se rend avec son titre et son champ fichier, et ne
   contient AUCUN attribut style inline. importApi est mocké. */

vi.mock('../api/importApi', () => ({
  default: { dryRun: vi.fn(), commit: vi.fn() },
}))

import ExcelImport from './ExcelImport'

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('ExcelImport (P169 — sans style inline)', () => {
  it('se rend (titre + champ fichier) sans style inline', () => {
    const { container } = render(
      <ExcelImport target="clients" onClose={vi.fn()} onDone={vi.fn()} />,
    )
    expect(screen.getByText(/Importer des clients/)).toBeInTheDocument()
    expect(container.querySelector('input[type="file"]')).toBeInTheDocument()
    expect(container.querySelectorAll('[style]')).toHaveLength(0)
  })
})
