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

/* NTUX8 — navigation clavier type tableur, 100 % opt-in (`autoEdit`/
   `onCommitNav`). Sans ces deux props, le comportement ci-dessus reste
   BYTE-IDENTIQUE (déjà couvert par les tests VX127 ci-dessus, qui ne les
   passent jamais). */
describe('EditableCell (NTUX8 — navigation clavier)', () => {
  it('Tab SANS onCommitNav garde le comportement natif (pas de preventDefault, pas de commit forcé)', () => {
    const onSave = vi.fn()
    render(<EditableCell value="12" onSave={onSave} />)
    fireEvent.doubleClick(screen.getByText('12'))
    const input = document.querySelector('input')
    fireEvent.change(input, { target: { value: '20' } })
    const event = fireEvent.keyDown(input, { key: 'Tab' })
    // `fireEvent.keyDown` renvoie `false` si `preventDefault()` a été appelé —
    // ici il ne doit PAS l'être (comportement natif préservé sans onCommitNav).
    expect(event).toBe(true)
    expect(onSave).not.toHaveBeenCalled()
  })

  it('Tab AVEC onCommitNav commit puis appelle onCommitNav("next")', async () => {
    const onSave = vi.fn().mockResolvedValue({})
    const onCommitNav = vi.fn()
    render(<EditableCell value="12" onSave={onSave} onCommitNav={onCommitNav} />)
    fireEvent.doubleClick(screen.getByText('12'))
    const input = document.querySelector('input')
    fireEvent.change(input, { target: { value: '20' } })
    fireEvent.keyDown(input, { key: 'Tab' })
    await waitFor(() => expect(onSave).toHaveBeenCalledWith('20', undefined))
    await waitFor(() => expect(onCommitNav).toHaveBeenCalledWith('next'))
  })

  it('Maj+Tab appelle onCommitNav("prev")', async () => {
    const onSave = vi.fn().mockResolvedValue({})
    const onCommitNav = vi.fn()
    render(<EditableCell value="12" onSave={onSave} onCommitNav={onCommitNav} />)
    fireEvent.doubleClick(screen.getByText('12'))
    fireEvent.change(document.querySelector('input'), { target: { value: '20' } })
    fireEvent.keyDown(document.querySelector('input'), { key: 'Tab', shiftKey: true })
    await waitFor(() => expect(onCommitNav).toHaveBeenCalledWith('prev'))
  })

  it('Entrée avec onCommitNav valide ET appelle onCommitNav("down")', async () => {
    const onSave = vi.fn().mockResolvedValue({})
    const onCommitNav = vi.fn()
    render(<EditableCell value="12" onSave={onSave} onCommitNav={onCommitNav} />)
    fireEvent.doubleClick(screen.getByText('12'))
    fireEvent.change(document.querySelector('input'), { target: { value: '20' } })
    fireEvent.keyDown(document.querySelector('input'), { key: 'Enter' })
    await waitFor(() => expect(onCommitNav).toHaveBeenCalledWith('down'))
  })

  it('une erreur de validation garde la cellule ouverte et N\'APPELLE PAS onCommitNav', async () => {
    const validate = () => 'Valeur invalide.'
    const onCommitNav = vi.fn()
    render(<EditableCell value="12" onSave={vi.fn()} validate={validate} onCommitNav={onCommitNav} />)
    fireEvent.doubleClick(screen.getByText('12'))
    fireEvent.change(document.querySelector('input'), { target: { value: 'x' } })
    fireEvent.keyDown(document.querySelector('input'), { key: 'Tab' })
    expect(await screen.findByText('Valeur invalide.')).toBeTruthy()
    expect(onCommitNav).not.toHaveBeenCalled()
    expect(document.querySelector('input')).not.toBeNull() // toujours en édition
  })

  it('autoEdit=true ouvre la cellule automatiquement sans double-clic', () => {
    render(<EditableCell value="12" onSave={vi.fn()} autoEdit />)
    expect(document.querySelector('input')).toHaveValue('12')
  })

  it('autoEdit=true sur une cellule readOnly n\'ouvre PAS l\'édition', () => {
    render(<EditableCell value="12" onSave={vi.fn()} autoEdit readOnly />)
    expect(document.querySelector('input')).toBeNull()
  })
})
