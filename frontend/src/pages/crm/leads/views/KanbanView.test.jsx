import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { StageMover } from './KanbanView'

/* J140 + L151 — alternative CLAVIER au glisser-déposer + enregistrement
   optimiste du changement d'étape. On vérifie : (1) un <select> d'étape
   accessible (avec label) est rendu ; (2) changer l'étape appelle le commit
   existant onInlineSave(lead, 'stage', valeur) ; (3) le libellé inline
   « Enregistrement… » s'affiche pendant le commit ; (4) un commit qui REJETTE
   restaure l'étape précédente (rollback). Aucune dépendance dnd-kit ici. */

vi.mock('../../../../ui/confirm', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

afterEach(() => { cleanup(); vi.clearAllMocks() })

const lead = { id: 7, nom: 'Test', stage: 'NEW' }

describe('KanbanView · StageMover (J140 clavier + L151 optimiste)', () => {
  it('rend un sélecteur d’étape accessible', () => {
    render(<StageMover lead={lead} onInlineSave={vi.fn(() => Promise.resolve())} />)
    const select = screen.getByLabelText(/Changer l'étape/)
    expect(select.tagName).toBe('SELECT')
    expect(select).toHaveValue('NEW')
  })

  it('ne rend rien si onInlineSave est absent (lecture seule)', () => {
    const { container } = render(<StageMover lead={lead} onInlineSave={undefined} />)
    expect(container.querySelector('select')).toBeNull()
  })

  it('appelle onInlineSave avec la nouvelle étape et affiche « Enregistrement… »', async () => {
    let resolveCommit
    const onInlineSave = vi.fn(
      () => new Promise((res) => { resolveCommit = res }),
    )
    render(<StageMover lead={lead} onInlineSave={onInlineSave} />)
    fireEvent.change(screen.getByLabelText(/Changer l'étape/), {
      target: { value: 'CONTACTED' },
    })
    expect(onInlineSave).toHaveBeenCalledWith(lead, 'stage', 'CONTACTED')
    // Pendant le commit : libellé inline + valeur optimiste affichée.
    await waitFor(() => expect(screen.getByText('Enregistrement…')).toBeInTheDocument())
    expect(screen.getByLabelText(/Changer l'étape/)).toHaveValue('CONTACTED')
    resolveCommit()
  })

  it('restaure l’étape précédente si le commit rejette (rollback)', async () => {
    const onInlineSave = vi.fn(() => Promise.reject(new Error('boom')))
    render(<StageMover lead={lead} onInlineSave={onInlineSave} />)
    fireEvent.change(screen.getByLabelText(/Changer l'étape/), {
      target: { value: 'SIGNED' },
    })
    await waitFor(() => expect(onInlineSave).toHaveBeenCalled())
    await waitFor(() =>
      expect(screen.getByLabelText(/Changer l'étape/)).toHaveValue('NEW'))
  })
})
