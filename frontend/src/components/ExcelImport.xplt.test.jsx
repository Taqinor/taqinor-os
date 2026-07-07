import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* XPLT1 — mode d'import (créer/maj/upsert) envoyé au commit.
   XPLT2 — mapping sauvegardé (sélecteur + sauvegarde) + lien CSV des lignes
   en échec après un commit partiel. */

const {
  dryRun, commit, getSavedMappings, saveMapping, jobErreursCsv,
  downloadBlob, filenameFromResponse,
} = vi.hoisted(() => ({
  dryRun: vi.fn(() => Promise.resolve({
    data: {
      mapping: { Nom: 'nom', Email: 'email' },
      non_mappees: [],
      apercu: [{ nom: 'Karim', email: 'karim@x.ma' }],
      total_lignes: 1,
    },
  })),
  commit: vi.fn(() => Promise.resolve({
    data: { created: 0, updated: 1, skipped: [{ ligne: 2, raison: 'doublon' }], job_id: 42 },
  })),
  getSavedMappings: vi.fn(() => Promise.resolve({
    data: [{ id: 1, target: 'leads', nom: 'Export CRM X', mapping: { Nom: 'nom' } }],
  })),
  saveMapping: vi.fn(() => Promise.resolve({ data: {} })),
  jobErreursCsv: vi.fn(() => Promise.resolve({ data: new Blob(['x']), headers: {} })),
  downloadBlob: vi.fn(),
  filenameFromResponse: vi.fn(() => 'import_42_erreurs.csv'),
}))

vi.mock('../api/importApi', () => ({
  default: { dryRun, commit, getSavedMappings, saveMapping, jobErreursCsv },
  downloadBlob,
  filenameFromResponse,
}))

import ExcelImport from './ExcelImport'

afterEach(() => { cleanup(); vi.clearAllMocks() })

function makeFile() {
  return new File(['Nom,Email\nKarim,karim@x.ma\n'], 'leads.csv', { type: 'text/csv' })
}

describe('ExcelImport — XPLT1 mode + XPLT2 mapping/erreurs CSV', () => {
  it('propose le sélecteur de mapping sauvegardé et le mode d\'import', async () => {
    render(<ExcelImport target="leads" onClose={vi.fn()} onDone={vi.fn()} />)

    await waitFor(() => expect(getSavedMappings).toHaveBeenCalledWith('leads'))
    expect(screen.getByLabelText("Mode d'import")).toBeInTheDocument()
    expect(await screen.findByLabelText('Mapping sauvegardé')).toBeInTheDocument()
    expect(screen.getByText('Export CRM X')).toBeInTheDocument()
  })

  it('envoie le mode choisi au commit', async () => {
    const user = userEvent.setup()
    render(<ExcelImport target="leads" onClose={vi.fn()} onDone={vi.fn()} />)

    const fileInput = document.querySelector('input[type="file"]')
    await user.upload(fileInput, makeFile())
    await screen.findByRole('button', { name: 'Sauvegarder ce mapping' })

    await user.selectOptions(screen.getByLabelText("Mode d'import"), 'upsert')
    await user.click(screen.getByRole('button', { name: /Importer 1 ligne/ }))

    await waitFor(() => expect(commit).toHaveBeenCalled())
    expect(commit.mock.calls[0][2]).toMatchObject({ mode: 'upsert' })
  })

  it('sauvegarde le mapping courant sous un nom', async () => {
    const user = userEvent.setup()
    render(<ExcelImport target="leads" onClose={vi.fn()} onDone={vi.fn()} />)

    const fileInput = document.querySelector('input[type="file"]')
    await user.upload(fileInput, makeFile())
    await screen.findByRole('button', { name: 'Sauvegarder ce mapping' })

    await user.type(screen.getByLabelText('Nom du mapping à sauvegarder'), 'Mon mapping')
    await user.click(screen.getByRole('button', { name: 'Sauvegarder ce mapping' }))

    await waitFor(() => expect(saveMapping).toHaveBeenCalledWith(
      'leads', 'Mon mapping', { Nom: 'nom', Email: 'email' }))
  })

  it('propose le CSV des lignes en échec après un commit partiel', async () => {
    const user = userEvent.setup()
    render(<ExcelImport target="leads" onClose={vi.fn()} onDone={vi.fn()} />)

    const fileInput = document.querySelector('input[type="file"]')
    await user.upload(fileInput, makeFile())
    await screen.findByRole('button', { name: 'Sauvegarder ce mapping' })
    await user.click(screen.getByRole('button', { name: /Importer 1 ligne/ }))

    const csvBtn = await screen.findByRole('button', { name: 'Télécharger le CSV des lignes en échec' })
    await user.click(csvBtn)

    await waitFor(() => expect(jobErreursCsv).toHaveBeenCalledWith(42))
    expect(downloadBlob).toHaveBeenCalled()
  })
})
