import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* WIR199 — /fpa/administration : jusqu'ici cycle ET département devaient
   être créés en admin Django (SaisiePage exige les deux mais n'a aucun
   moyen de les créer). Cet écran ferme le trou : arbre départements CRUD +
   cycles (création, ouvrir-saisie/clore/dupliquer/export XLSX blob). */

const getDepartementsTree = vi.fn()
const createDepartement = vi.fn()
const updateDepartement = vi.fn()
const deleteDepartement = vi.fn()
const getCycles = vi.fn()
const createCycle = vi.fn()
const ouvrirSaisie = vi.fn()
const cloreCycle = vi.fn()
const dupliquerCycle = vi.fn()
const exportCycle = vi.fn()

vi.mock('../../api/fpaApi', () => ({
  default: {
    getDepartementsTree: (...a) => getDepartementsTree(...a),
    createDepartement: (...a) => createDepartement(...a),
    updateDepartement: (...a) => updateDepartement(...a),
    deleteDepartement: (...a) => deleteDepartement(...a),
    getCycles: (...a) => getCycles(...a),
    createCycle: (...a) => createCycle(...a),
    ouvrirSaisie: (...a) => ouvrirSaisie(...a),
    cloreCycle: (...a) => cloreCycle(...a),
    dupliquerCycle: (...a) => dupliquerCycle(...a),
    exportCycle: (...a) => exportCycle(...a),
  },
}))

const downloadBlob = vi.fn()
vi.mock('../../utils/downloadBlob', () => ({ downloadBlob: (...a) => downloadBlob(...a) }))

import AdministrationPage from './AdministrationPage'

beforeEach(() => {
  vi.clearAllMocks()
  window.confirm = vi.fn(() => true)
  getDepartementsTree.mockResolvedValue({
    data: [{ id: 1, code: 'COM', nom: 'Commercial', actif: true, enfants: [] }],
  })
  createDepartement.mockResolvedValue({ data: { id: 2 } })
  getCycles.mockResolvedValue({
    data: [{ id: 7, nom: 'Budget 2026', statut: 'brouillon' }],
  })
  createCycle.mockResolvedValue({ data: { id: 8 } })
  ouvrirSaisie.mockResolvedValue({ data: {} })
  cloreCycle.mockResolvedValue({ data: {} })
  dupliquerCycle.mockResolvedValue({ data: {} })
  exportCycle.mockResolvedValue({ data: new Blob(['x']) })
})

describe('AdministrationPage (WIR199)', () => {
  it('affiche l’arbre des départements et en crée un', async () => {
    const user = userEvent.setup()
    render(<AdministrationPage />)
    await screen.findByText('COM — Commercial')

    await user.type(screen.getByLabelText('Code du département'), 'TEC')
    await user.type(screen.getByLabelText('Nom du département'), 'Technique')
    await user.click(screen.getByRole('button', { name: 'Créer le département' }))

    await waitFor(() => expect(createDepartement).toHaveBeenCalledWith(expect.objectContaining({
      code: 'TEC', nom: 'Technique',
    })))
  })

  it('crée un cycle budgétaire', async () => {
    const user = userEvent.setup()
    render(<AdministrationPage />)
    await screen.findByText(/Budget 2026/)

    await user.type(screen.getByLabelText('Nom du cycle'), 'Budget 2027')
    await user.type(screen.getByLabelText('Date de début du cycle'), '2027-01-01')
    await user.type(screen.getByLabelText('Date de fin du cycle'), '2027-12-31')
    await user.click(screen.getByRole('button', { name: 'Créer le cycle' }))

    await waitFor(() => expect(createCycle).toHaveBeenCalledWith(expect.objectContaining({
      nom: 'Budget 2027', date_debut: '2027-01-01', date_fin: '2027-12-31',
    })))
  })

  it('ouvre la saisie, clôture, duplique et exporte un cycle', async () => {
    const user = userEvent.setup()
    render(<AdministrationPage />)
    await screen.findByText(/Budget 2026/)

    await user.click(screen.getByRole('button', { name: 'Ouvrir la saisie' }))
    await waitFor(() => expect(ouvrirSaisie).toHaveBeenCalledWith(7))

    await user.click(screen.getByRole('button', { name: 'Clore' }))
    await waitFor(() => expect(cloreCycle).toHaveBeenCalledWith(7))

    await user.click(screen.getByRole('button', { name: 'Dupliquer' }))
    await waitFor(() => expect(dupliquerCycle).toHaveBeenCalledWith(7, expect.any(String)))

    await user.click(screen.getByRole('button', { name: 'Exporter XLSX' }))
    await waitFor(() => expect(exportCycle).toHaveBeenCalledWith(7))
    await waitFor(() => expect(downloadBlob).toHaveBeenCalled())
  })
})
