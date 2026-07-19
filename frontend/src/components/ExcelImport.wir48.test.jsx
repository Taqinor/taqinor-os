import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* WIR48 — cibles véhicules/contrats/dossiers_rh ajoutées + modes maj/upsert
   masqués hors leads/clients (le serveur les refuse pour ces cibles). */

const { dryRun, commit, getSavedMappings } = vi.hoisted(() => ({
  dryRun: vi.fn(() => Promise.resolve({
    data: {
      mapping: { Immat: 'immatriculation' }, non_mappees: [],
      apercu: [{ immatriculation: '12345-A-6' }], total_lignes: 1,
    },
  })),
  commit: vi.fn(() => Promise.resolve({ data: { created: 1, skipped: [] } })),
  getSavedMappings: vi.fn(() => Promise.resolve({ data: [] })),
}))

vi.mock('../api/importApi', () => ({
  default: { dryRun, commit, getSavedMappings, saveMapping: vi.fn(), jobErreursCsv: vi.fn() },
  downloadBlob: vi.fn(),
  filenameFromResponse: vi.fn(() => 'f.csv'),
}))

import ExcelImport from './ExcelImport'

afterEach(() => { cleanup(); vi.clearAllMocks() })

function vehiculeFile() {
  return new File(['Immat\n12345-A-6\n'], 'vehicules.csv', { type: 'text/csv' })
}

describe('ExcelImport — WIR48', () => {
  it('affiche le libellé « véhicules » et masque le sélecteur de mode', () => {
    render(<ExcelImport target="vehicules" onClose={vi.fn()} onDone={vi.fn()} />)
    expect(screen.getByText(/Importer des véhicules/)).toBeInTheDocument()
    // maj/upsert non supportés → pas de sélecteur de mode du tout.
    expect(screen.queryByLabelText("Mode d'import")).not.toBeInTheDocument()
  })

  it('commit une cible véhicules en mode « creer » (jamais maj/upsert)', async () => {
    const user = userEvent.setup()
    render(<ExcelImport target="vehicules" onClose={vi.fn()} onDone={vi.fn()} />)

    const fileInput = document.querySelector('input[type="file"]')
    await user.upload(fileInput, vehiculeFile())
    await user.click(await screen.findByRole('button', { name: /Importer 1 ligne/ }))

    await waitFor(() => expect(commit).toHaveBeenCalled())
    expect(commit.mock.calls[0][2]).toMatchObject({ mode: 'creer' })
  })

  it('conserve le sélecteur de mode pour leads (maj/upsert supportés)', () => {
    render(<ExcelImport target="leads" onClose={vi.fn()} onDone={vi.fn()} />)
    expect(screen.getByLabelText("Mode d'import")).toBeInTheDocument()
  })
})
