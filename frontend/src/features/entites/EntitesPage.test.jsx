import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

vi.mock('./entitesApi', () => ({
  default: {
    tree: vi.fn(() => Promise.resolve({ data: [
      { id: 1, code: 'HOLD', nom: 'Holding', actif: true, enfants: [] },
    ] })),
    list: vi.fn(() => Promise.resolve({ data: [] })),
    update: vi.fn(() => Promise.resolve({ data: {} })),
    desactiver: vi.fn(() => Promise.resolve({ data: {} })),
    historique: vi.fn(() => Promise.resolve({ data: [
      { id: 10, kind: 'note', body: 'Première note', created_by: 'sami' },
    ] })),
    noter: vi.fn(() => Promise.resolve({ data: { ok: true } })),
    export: vi.fn(() => Promise.resolve({ data: new Blob(['x']) })),
    importer: vi.fn(() => Promise.resolve({ data: { crees: 2, mis_a_jour: 0, erreurs: [] } })),
  },
}))
vi.mock('../../api/importApi', () => ({ downloadXlsx: vi.fn() }))
vi.mock('../../lib/toast', () => ({
  toastError: vi.fn(), toastSuccess: vi.fn(),
}))

import entitesApi from './entitesApi'
import { downloadXlsx } from '../../api/importApi'
import EntitesPage from './EntitesPage'

describe('EntitesPage (WIR68)', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('exporte le référentiel en xlsx', async () => {
    render(<EntitesPage />)
    fireEvent.click(await screen.findByRole('button', { name: /Exporter/ }))
    await waitFor(() => expect(entitesApi.export).toHaveBeenCalled())
    await waitFor(() => expect(downloadXlsx).toHaveBeenCalled())
  })

  it('ouvre l\'historique et permet de noter', async () => {
    render(<EntitesPage />)
    fireEvent.click(await screen.findByRole('button', { name: /Historique/ }))
    expect(await screen.findByText('Première note')).toBeInTheDocument()
    expect(entitesApi.historique).toHaveBeenCalledWith(1)

    fireEvent.change(screen.getByLabelText('Ajouter une note'), {
      target: { value: 'Nouvelle note' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Noter' }))
    await waitFor(() =>
      expect(entitesApi.noter).toHaveBeenCalledWith(1, 'Nouvelle note'))
  })

  it('importe un CSV (dry-run puis commit après confirmation)', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    render(<EntitesPage />)
    await screen.findByText('Holding')
    const input = screen.getByLabelText("Importer un fichier CSV d'entités")
    const file = new File(['code,nom\nAG1,Agence 1'], 'entites.csv', { type: 'text/csv' })
    fireEvent.change(input, { target: { files: [file] } })
    await waitFor(() =>
      expect(entitesApi.importer).toHaveBeenCalledWith(file, false))
    await waitFor(() =>
      expect(entitesApi.importer).toHaveBeenCalledWith(file, true))
  })
})
