import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { EditableCell } from './EditableCell'

/* VX127 — L'état LECTURE-SEULE existe enfin + EditableCell honnête. Trois
   états auparavant absents : readOnly (distinct de disabled — double-clic
   sans effet), l'enregistrement en cours (spinner pendant `await onSave`),
   et le rejet serveur (la cellule REROUVRE avec un message au lieu de se
   refermer en silence). */
describe('EditableCell (VX127)', () => {
  it('readOnly : double-clic et Entrée/F2 sans effet, aucun mode édition', () => {
    const onSave = vi.fn()
    render(<EditableCell value="12" onSave={onSave} readOnly />)
    const cell = screen.getByText('12')
    fireEvent.doubleClick(cell)
    expect(document.querySelector('input')).toBeNull()
    fireEvent.keyDown(cell, { key: 'Enter' })
    expect(document.querySelector('input')).toBeNull()
    fireEvent.keyDown(cell, { key: 'F2' })
    expect(document.querySelector('input')).toBeNull()
    expect(onSave).not.toHaveBeenCalled()
    // Pas de titre « Double-cliquez pour modifier » sur une cellule readOnly.
    expect(cell).not.toHaveAttribute('title')
  })

  it('enregistrement en cours : un spinner discret pendant `await onSave`', async () => {
    let resolveSave
    const onSave = vi.fn(() => new Promise((resolve) => { resolveSave = resolve }))
    render(<EditableCell value="12" onSave={onSave} />)
    fireEvent.doubleClick(screen.getByText('12'))
    const input = document.querySelector('input')
    fireEvent.change(input, { target: { value: '20' } })
    fireEvent.keyDown(input, { key: 'Enter' })

    // Pendant l'attente : le spinner remplace les boutons Valider/Annuler.
    expect(await screen.findByRole('status')).toBeTruthy()
    expect(screen.queryByLabelText('Valider')).toBeNull()
    expect(screen.queryByLabelText('Annuler')).toBeNull()

    resolveSave({})
    await waitFor(() => expect(screen.queryByRole('status')).toBeNull())
  })

  it('rejet serveur : la cellule REROUVRE avec un message, ne se ferme pas en silence', async () => {
    const onSave = vi.fn().mockRejectedValue({ response: { data: { detail: 'Stock insuffisant.' } } })
    render(<EditableCell value="12" onSave={onSave} />)
    fireEvent.doubleClick(screen.getByText('12'))
    const input = document.querySelector('input')
    fireEvent.change(input, { target: { value: '999' } })
    fireEvent.keyDown(input, { key: 'Enter' })

    expect(await screen.findByText('Stock insuffisant.')).toBeTruthy()
    // Toujours en édition (rouverte) : le champ existe encore avec le brouillon.
    expect(document.querySelector('input')).toHaveValue('999')
  })
})
