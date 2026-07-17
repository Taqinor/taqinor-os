// NTUX20 — BulkNoteDialog : prévisualisation des enregistrements touchés,
// note requise avant confirmation, échec partiel n'annule pas le reste.
// Même contrat de test que BulkEditDialog.test.jsx (NTUX5).
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import BulkNoteDialog from './BulkNoteDialog'

const ROWS = [
  { id: 1, ref: 'TCK-001' },
  { id: 2, ref: 'TCK-002' },
  { id: 3, ref: 'TCK-003' },
]

afterEach(() => cleanup())

describe('BulkNoteDialog (NTUX20)', () => {
  it('affiche la prévisualisation du nombre d\'enregistrements touchés', () => {
    render(
      <BulkNoteDialog
        open onOpenChange={() => {}} rows={ROWS}
        getRowLabel={(r) => r.ref} onConfirm={vi.fn()}
      />,
    )
    expect(screen.getByText(/3 enregistrements/)).toBeInTheDocument()
    expect(screen.getAllByTestId('bnd-preview-row')).toHaveLength(3)
    expect(screen.getByText('TCK-001')).toBeInTheDocument()
  })

  it('« Confirmer » est désactivé tant qu\'aucune note n\'est saisie', () => {
    render(
      <BulkNoteDialog open onOpenChange={() => {}} rows={ROWS} onConfirm={vi.fn()} />,
    )
    expect(screen.getByRole('button', { name: 'Confirmer' })).toBeDisabled()
  })

  it('« Confirmer » appelle onConfirm(rows, note TRIMMÉE) puis ferme si tout réussit', async () => {
    const user = userEvent.setup()
    const onConfirm = vi.fn().mockResolvedValue({
      updated: ROWS.map((r) => ({ id: r.id })),
      failed: [],
    })
    const onOpenChange = vi.fn()
    const onDone = vi.fn()
    render(
      <BulkNoteDialog
        open onOpenChange={onOpenChange} rows={ROWS}
        onConfirm={onConfirm} onDone={onDone}
      />,
    )
    await user.type(screen.getByLabelText('Contenu de la note'), '  Relance client groupée  ')
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }))
    await waitFor(() => expect(onConfirm).toHaveBeenCalledWith(ROWS, 'Relance client groupée'))
    await waitFor(() => expect(onOpenChange).toHaveBeenCalledWith(false))
    expect(onDone).toHaveBeenCalled()
  })

  it('un échec partiel affiche la raison et n\'annule pas les enregistrements réussis (reste ouvert)', async () => {
    const user = userEvent.setup()
    const onConfirm = vi.fn().mockResolvedValue({
      updated: [{ id: 1 }, { id: 2 }],
      failed: [{ id: 3, label: 'TCK-003', reason: 'ticket clôturé' }],
    })
    const onOpenChange = vi.fn()
    render(
      <BulkNoteDialog open onOpenChange={onOpenChange} rows={ROWS} onConfirm={onConfirm} />,
    )
    await user.type(screen.getByLabelText('Contenu de la note'), 'Note de suivi')
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }))
    expect(await screen.findByTestId('bnd-result')).toBeInTheDocument()
    expect(screen.getByText(/ticket clôturé/)).toBeInTheDocument()
    expect(screen.getByText(/2 enregistrements/)).toBeInTheDocument()
    // Reste ouvert pour que l'utilisateur voie l'échec — jamais de fermeture auto.
    expect(onOpenChange).not.toHaveBeenCalledWith(false)
  })

  it('« Annuler » ferme sans appeler onConfirm et réinitialise la note à la réouverture', async () => {
    const user = userEvent.setup()
    const onConfirm = vi.fn()
    const onOpenChange = vi.fn()
    render(
      <BulkNoteDialog open onOpenChange={onOpenChange} rows={ROWS} onConfirm={onConfirm} />,
    )
    await user.type(screen.getByLabelText('Contenu de la note'), 'brouillon abandonné')
    fireEvent.click(screen.getByRole('button', { name: 'Annuler' }))
    expect(onOpenChange).toHaveBeenCalledWith(false)
    expect(onConfirm).not.toHaveBeenCalled()
  })

  it('une note composée uniquement d\'espaces ne peut pas être confirmée', async () => {
    const user = userEvent.setup()
    render(
      <BulkNoteDialog open onOpenChange={() => {}} rows={ROWS} onConfirm={vi.fn()} />,
    )
    await user.type(screen.getByLabelText('Contenu de la note'), '   ')
    expect(screen.getByRole('button', { name: 'Confirmer' })).toBeDisabled()
  })
})
