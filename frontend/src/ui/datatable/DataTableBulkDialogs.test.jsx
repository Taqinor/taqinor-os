// PACT174 — les trois tiroirs livrés avec le moteur (BulkEditDialog/NTUX5,
// BulkNoteDialog/NTUX20, ViewBuilderWizard+FilterBuilder/NTUX25) étaient
// testés unitairement mais montés NULLE PART. Ce fichier garde le CÂBLAGE :
// que le moteur les ouvre bien depuis la barre de sélection et la barre
// d'outils, qu'il n'écrive rien avant confirmation, et — surtout — qu'un
// écran qui ne fournit AUCUNE des trois props rende exactement comme avant.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import { setStoredDensity } from '../../design/theme.js'

import { DataTable } from './DataTable.jsx'

function wrapper({ children }) {
  return (
    <MemoryRouter>
      <ThemeProvider>{children}</ThemeProvider>
    </MemoryRouter>
  )
}

const DATA = [
  { id: 1, reference: 'TIC-001', statut: 'nouveau' },
  { id: 2, reference: 'TIC-002', statut: 'planifie' },
]

const COLUMNS = [
  { id: 'reference', header: 'Référence' },
  { id: 'statut', header: 'Statut' },
]

const BULK_EDIT = {
  fieldLabel: 'Statut',
  options: [
    { value: 'planifie', label: 'Planifié' },
    { value: 'cloture', label: 'Clôturé' },
  ],
  getRowLabel: (row) => row.reference,
  getOldValue: (row) => row.statut,
}

function renderTable(props = {}) {
  return render(
    <DataTable data={DATA} columns={COLUMNS} getRowId={(r) => r.id} selectable {...props} />,
    { wrapper },
  )
}

async function selectFirstRow(user) {
  await user.click(screen.getAllByLabelText(/Sélectionner la ligne/)[0])
}

beforeEach(() => {
  setStoredDensity('comfortable')
})

/* ====================== bulkEdit — aperçu AVANT/APRÈS ====================== */

describe('PACT174 — `bulkEdit` monte BulkEditDialog (NTUX5)', () => {
  it('ajoute une action par valeur cible et N\'ÉCRIT RIEN au clic', async () => {
    const user = userEvent.setup()
    const onConfirm = vi.fn().mockResolvedValue({ updated: [{ id: 1 }], failed: [] })
    renderTable({ bulkEdit: { ...BULK_EDIT, onConfirm } })

    await selectFirstRow(user)
    await user.click(screen.getByRole('button', { name: 'Statut → Planifié' }))

    // Le tiroir s'ouvre sur l'aperçu ; aucune écriture tant que « Confirmer »
    // n'a pas été cliqué.
    expect(screen.getAllByTestId('bed-preview-row')).toHaveLength(1)
    expect(onConfirm).not.toHaveBeenCalled()
  })

  it('confirme avec (lignes sélectionnées, valeur choisie)', async () => {
    const user = userEvent.setup()
    const onConfirm = vi.fn().mockResolvedValue({ updated: [{ id: 1 }], failed: [] })
    renderTable({ bulkEdit: { ...BULK_EDIT, onConfirm } })

    await selectFirstRow(user)
    await user.click(screen.getByRole('button', { name: 'Statut → Clôturé' }))
    await user.click(screen.getByRole('button', { name: 'Confirmer' }))

    await waitFor(() => expect(onConfirm).toHaveBeenCalledTimes(1))
    const [rows, newValue] = onConfirm.mock.calls[0]
    expect(rows.map((r) => r.reference)).toEqual(['TIC-001'])
    expect(newValue).toBe('cloture')
  })

  it('garde le tiroir ouvert et nomme les échecs sur un échec partiel', async () => {
    const user = userEvent.setup()
    const onConfirm = vi.fn().mockResolvedValue({
      updated: [], failed: [{ id: 1, label: 'TIC-001', reason: 'Transition refusée.' }],
    })
    renderTable({ bulkEdit: { ...BULK_EDIT, onConfirm } })

    await selectFirstRow(user)
    await user.click(screen.getByRole('button', { name: 'Statut → Planifié' }))
    await user.click(screen.getByRole('button', { name: 'Confirmer' }))

    await waitFor(() => expect(screen.getByTestId('bed-result')).toBeInTheDocument())
    expect(screen.getByText(/Transition refusée\./)).toBeInTheDocument()
  })
})

/* ========================= bulkNote — note groupée ========================= */

describe('PACT174 — `bulkNote` monte BulkNoteDialog (NTUX20)', () => {
  it('ouvre le tiroir de note et confirme avec (lignes, note)', async () => {
    const user = userEvent.setup()
    const onConfirm = vi.fn().mockResolvedValue({ updated: [{ id: 1 }], failed: [] })
    renderTable({ bulkNote: { getRowLabel: (row) => row.reference, onConfirm } })

    await selectFirstRow(user)
    await user.click(screen.getByRole('button', { name: 'Ajouter une note' }))
    expect(screen.getAllByTestId('bnd-preview-row')).toHaveLength(1)

    await user.type(screen.getByLabelText('Contenu de la note'), 'Relance client')
    await user.click(screen.getByRole('button', { name: 'Confirmer' }))

    await waitFor(() => expect(onConfirm).toHaveBeenCalledTimes(1))
    const [rows, note] = onConfirm.mock.calls[0]
    expect(rows.map((r) => r.reference)).toEqual(['TIC-001'])
    expect(note).toBe('Relance client')
  })
})

/* =================== viewBuilder — assistant de vue ======================== */

describe('PACT174 — `viewBuilder` monte ViewBuilderWizard + FilterBuilder (NTUX25)', () => {
  it('« Nouvelle vue » ouvre l\'assistant sur les colonnes du moteur', async () => {
    const user = userEvent.setup()
    renderTable({ viewBuilder: { ecran: 'sav.tickets', onCreate: vi.fn() } })

    await user.click(screen.getByRole('button', { name: /Nouvelle vue/ }))
    const wizard = within(screen.getByTestId('view-builder-wizard'))
    // Étape 1 : les colonnes proposées sont celles déjà déclarées à <DataTable>.
    expect(wizard.getByLabelText('Référence')).toBeInTheDocument()
    expect(wizard.getByLabelText('Statut')).toBeInTheDocument()
  })

  it('l\'étape 2 rend le constructeur de filtres (FilterBuilder)', async () => {
    const user = userEvent.setup()
    renderTable({ viewBuilder: { ecran: 'sav.tickets', onCreate: vi.fn() } })

    await user.click(screen.getByRole('button', { name: /Nouvelle vue/ }))
    const wizard = within(screen.getByTestId('view-builder-wizard'))
    await user.click(wizard.getByRole('button', { name: /Suivant/ }))
    expect(wizard.getByTestId('filter-builder')).toBeInTheDocument()
  })

  it('crée la vue avec écran + nom + configuration, puis referme', async () => {
    const user = userEvent.setup()
    const onCreate = vi.fn().mockResolvedValue({})
    renderTable({ viewBuilder: { ecran: 'sav.tickets', onCreate } })

    await user.click(screen.getByRole('button', { name: /Nouvelle vue/ }))
    const wizard = within(screen.getByTestId('view-builder-wizard'))
    await user.click(wizard.getByRole('button', { name: /Suivant/ }))
    await user.click(wizard.getByRole('button', { name: /Suivant/ }))
    await user.type(wizard.getByRole('textbox'), 'Tickets en retard')
    await user.click(wizard.getByRole('button', { name: /Créer la vue/ }))

    await waitFor(() => expect(onCreate).toHaveBeenCalledTimes(1))
    const payload = onCreate.mock.calls[0][0]
    expect(payload.ecran).toBe('sav.tickets')
    expect(payload.nom).toBe('Tickets en retard')
    expect(payload.configuration.colonnes_visibles).toEqual(['reference', 'statut'])
    await waitFor(() => expect(screen.queryByTestId('view-builder-wizard')).toBeNull())
  })
})

/* ===================== Non-régression : rien sans props ==================== */

describe('PACT174 — 100 % opt-in', () => {
  it('sans `bulkEdit`/`bulkNote`, la barre de sélection ne gagne aucune action', async () => {
    const user = userEvent.setup()
    renderTable({ bulkActions: () => [{ id: 'suppr', label: 'Supprimer' }] })

    await selectFirstRow(user)
    expect(screen.getByRole('button', { name: 'Supprimer' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Ajouter une note' })).toBeNull()
    expect(screen.queryByRole('button', { name: /Statut → / })).toBeNull()
  })

  it('sans `viewBuilder`, aucun bouton « Nouvelle vue » dans la barre d\'outils', () => {
    renderTable()
    expect(screen.queryByRole('button', { name: /Nouvelle vue/ })).toBeNull()
  })
})
