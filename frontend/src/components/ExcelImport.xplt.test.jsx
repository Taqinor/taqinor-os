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
    // Changer de mode relance l'aperçu (il doit annoncer les écrasements du
    // NOUVEAU mode) : on attend ce 2e dry-run avant de valider.
    await waitFor(() => expect(dryRun).toHaveBeenCalledTimes(2))
    await user.click(screen.getByRole('button', { name: /Importer 1 ligne/ }))

    await waitFor(() => expect(commit).toHaveBeenCalled())
    // Garde-fou : le commit part SANS `ecraser` tant que la case n'est pas
    // cochée — un import ne remplace jamais une valeur saisie par défaut.
    expect(commit.mock.calls[0][2]).toMatchObject({ mode: 'upsert', ecraser: false })

    // La case « écraser » n'apparaît qu'en mode maj/upsert, jamais cochée.
    expect(screen.getByRole('checkbox')).not.toBeChecked()
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

  it("montre champ par champ ce que le fichier écraserait, avant l'import", async () => {
    const user = userEvent.setup()
    dryRun.mockResolvedValueOnce({
      data: {
        mapping: { Nom: 'nom', Ville: 'ville' },
        non_mappees: [],
        apercu: [{ nom: 'Bennani', ville: 'Casablanca' }],
        total_lignes: 1,
        mode: 'upsert',
        ecraser: false,
        ecrasements_total: 1,
        lignes_ecrasees: 1,
        ecrasements_appliques: 0,
        conflits_tronques: false,
        resume: { creation: 0, mise_a_jour: 1, ignoree: 0 },
        conflits: [{
          ligne: 1,
          action: 'mise_a_jour',
          raison: null,
          cible: 'crm.lead',
          cible_id: 7,
          cible_libelle: 'Bennani',
          ecrasements: [{ champ: 'ville', ancienne: 'Rabat', nouvelle: 'Casablanca' }],
          remplissages: [],
        }],
      },
    })
    render(<ExcelImport target="leads" onClose={vi.fn()} onDone={vi.fn()} />)

    const fileInput = document.querySelector('input[type="file"]')
    await user.upload(fileInput, makeFile())
    await screen.findByRole('button', { name: 'Sauvegarder ce mapping' })

    // L'ancienne valeur réelle ET la valeur du fichier sont toutes deux
    // affichées : l'utilisateur voit ce qu'il détruirait avant de cliquer.
    expect(screen.getByText('Rabat')).toBeInTheDocument()
    expect(screen.getByText(/Elles seront CONSERVÉES/)).toBeInTheDocument()
  })
})
