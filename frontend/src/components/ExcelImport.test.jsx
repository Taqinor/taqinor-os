import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'

/* P169 — ExcelImport : refonte sans style={} en dur (Tailwind/tokens). Test de
   non-régression : le modal se rend avec son titre et son champ fichier, et ne
   contient AUCUN attribut style inline. importApi est mocké. */

vi.mock('../api/importApi', () => ({
  default: {
    dryRun: vi.fn(),
    commit: vi.fn(),
    getSavedMappings: vi.fn(() => Promise.resolve({ data: [] })),
    saveMapping: vi.fn(),
    jobErreursCsv: vi.fn(),
  },
  downloadBlob: vi.fn(),
  filenameFromResponse: vi.fn(),
}))

import ExcelImport from './ExcelImport'
import importApi from '../api/importApi'

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

describe('ExcelImport (AERR75 — fond inerte pendant l’import)', () => {
  it('clic sur le fond pendant l’import : fenêtre gardée, résultat affiché', async () => {
    importApi.dryRun.mockResolvedValueOnce({ data: {
      mapping: { Nom: 'nom' }, non_mappees: [], apercu: [{ nom: 'Karim' }], total_lignes: 1,
    } })
    let resoudre
    importApi.commit.mockReturnValueOnce(new Promise((r) => { resoudre = r }))
    const onClose = vi.fn()
    const { container } = render(<ExcelImport target="clients" onClose={onClose} onDone={vi.fn()} />)
    fireEvent.change(container.querySelector('input[type="file"]'), {
      target: { files: [new File(['Nom\nKarim\n'], 'c.csv', { type: 'text/csv' })] },
    })
    fireEvent.click(await screen.findByRole('button', { name: /Importer 1 ligne/ }))
    await waitFor(() => expect(importApi.commit).toHaveBeenCalled())

    fireEvent.click(container.firstChild)
    expect(onClose).not.toHaveBeenCalled()

    resoudre({ data: { created: 1, skipped: [] } })
    expect(await screen.findByText(/créé\(s\)/)).toBeInTheDocument()
    fireEvent.click(container.firstChild)
    expect(onClose).toHaveBeenCalledTimes(1)
  })
})
