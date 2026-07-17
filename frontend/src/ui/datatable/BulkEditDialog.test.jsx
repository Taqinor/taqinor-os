// NTUX5 — BulkEditDialog : aperçu avant/après, confirmation explicite,
// échec partiel n'annule pas le reste.
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react'
import BulkEditDialog from './BulkEditDialog'

const ROWS = [
  { id: 1, ref: 'DEV-001', statut: 'brouillon' },
  { id: 2, ref: 'DEV-002', statut: 'envoye' },
]

afterEach(() => cleanup())

describe('BulkEditDialog (NTUX5)', () => {
  it('affiche l\'aperçu avant/après pour chaque ligne sélectionnée', () => {
    render(
      <BulkEditDialog
        open onOpenChange={() => {}} rows={ROWS} fieldLabel="Statut"
        getRowLabel={(r) => r.ref} getOldValue={(r) => r.statut} newValue="accepte"
        onConfirm={vi.fn()}
      />,
    )
    expect(screen.getAllByTestId('bed-preview-row')).toHaveLength(2)
    expect(screen.getByText('DEV-001')).toBeInTheDocument()
    expect(screen.getAllByText('accepte')).toHaveLength(2) // colonne "Après" identique pour les 2 lignes
  })

  it('« Confirmer » appelle onConfirm(rows, newValue) puis ferme si tout réussit', async () => {
    const onConfirm = vi.fn().mockResolvedValue({
      updated: [{ id: 1, before: 'brouillon', after: 'accepte' }, { id: 2, before: 'envoye', after: 'accepte' }],
      failed: [],
    })
    const onOpenChange = vi.fn()
    const onDone = vi.fn()
    render(
      <BulkEditDialog
        open onOpenChange={onOpenChange} rows={ROWS} fieldLabel="Statut"
        getRowLabel={(r) => r.ref} getOldValue={(r) => r.statut} newValue="accepte"
        onConfirm={onConfirm} onDone={onDone}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }))
    await waitFor(() => expect(onConfirm).toHaveBeenCalledWith(ROWS, 'accepte'))
    await waitFor(() => expect(onOpenChange).toHaveBeenCalledWith(false))
    expect(onDone).toHaveBeenCalled()
  })

  it('un échec partiel affiche la raison et n\'annule pas les lignes réussies (reste ouvert)', async () => {
    const onConfirm = vi.fn().mockResolvedValue({
      updated: [{ id: 1, before: 'brouillon', after: 'accepte' }],
      failed: [{ id: 2, label: 'DEV-002', reason: 'transition invalide (déjà facturé)' }],
    })
    const onOpenChange = vi.fn()
    render(
      <BulkEditDialog
        open onOpenChange={onOpenChange} rows={ROWS} fieldLabel="Statut"
        getRowLabel={(r) => r.ref} getOldValue={(r) => r.statut} newValue="accepte"
        onConfirm={onConfirm}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }))
    expect(await screen.findByTestId('bed-result')).toBeInTheDocument()
    expect(screen.getByText(/transition invalide/)).toBeInTheDocument()
    expect(screen.getByText(/1 ligne mise à jour/)).toBeInTheDocument()
    // Reste ouvert pour que l'utilisateur voie l'échec — jamais de fermeture auto.
    expect(onOpenChange).not.toHaveBeenCalledWith(false)
  })

  it('« Confirmer » est désactivé sans ligne sélectionnée', () => {
    render(
      <BulkEditDialog
        open onOpenChange={() => {}} rows={[]} fieldLabel="Statut"
        getOldValue={() => ''} newValue="x" onConfirm={vi.fn()}
      />,
    )
    expect(screen.getByRole('button', { name: 'Confirmer' })).toBeDisabled()
  })
})
