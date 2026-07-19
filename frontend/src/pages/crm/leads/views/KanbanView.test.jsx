import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { StageMover } from './KanbanView'
import { toast } from '../../../../ui/confirm'
import { SIGNE_INTERCEPT } from '../signeIntercept'

/* J140 + L151 — alternative CLAVIER au glisser-déposer + enregistrement
   optimiste du changement d'étape. On vérifie : (1) un <select> d'étape
   accessible (avec label) est rendu ; (2) changer l'étape appelle le commit
   existant onInlineSave(lead, 'stage', valeur) ; (3) le libellé inline
   « Enregistrement… » s'affiche pendant le commit ; (4) un commit qui REJETTE
   restaure l'étape précédente (rollback). Aucune dépendance dnd-kit ici.
   LB3 — (5) le rejet SIGNE_INTERCEPT (SigneDialog qui s'ouvre) restaure SANS
   toaster ; (6) un vrai échec réseau restaure ET toaste (contrat inchangé). */

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

  it('restaure l’étape précédente si le commit rejette (rollback) et toaste', async () => {
    const onInlineSave = vi.fn(() => Promise.reject(new Error('boom')))
    render(<StageMover lead={lead} onInlineSave={onInlineSave} />)
    fireEvent.change(screen.getByLabelText(/Changer l'étape/), {
      target: { value: 'QUOTE_SENT' },
    })
    await waitFor(() => expect(onInlineSave).toHaveBeenCalled())
    await waitFor(() =>
      expect(screen.getByLabelText(/Changer l'étape/)).toHaveValue('NEW'))
    expect(toast.error).toHaveBeenCalledWith("Changement d'étape non enregistré — réessayez.")
  })

  it('LB3 : passer sur « Signé » rejette avec SIGNE_INTERCEPT — rollback SANS toast (bug #2)', async () => {
    const onInlineSave = vi.fn(() => Promise.reject(SIGNE_INTERCEPT))
    render(<StageMover lead={lead} onInlineSave={onInlineSave} />)
    fireEvent.change(screen.getByLabelText(/Changer l'étape/), {
      target: { value: 'SIGNED' },
    })
    await waitFor(() => expect(onInlineSave).toHaveBeenCalledWith(lead, 'stage', 'SIGNED'))
    // Le select revient honnêtement à l'étape réelle (fini le « Signé ✓
    // Enregistré » fantôme d'un faux Promise.resolve()).
    await waitFor(() =>
      expect(screen.getByLabelText(/Changer l'étape/)).toHaveValue('NEW'))
    expect(toast.error).not.toHaveBeenCalled()
  })

  it('LB4 : les options de recul sont grisées, COLD→actif reste sélectionnable (bug #7/#8)', () => {
    // Un lead FOLLOW_UP (rang 3) : reculer vers NEW/CONTACTED/QUOTE_SENT est
    // interdit (disabled), avancer vers SIGNED ou parker en COLD reste permis.
    render(
      <StageMover
        lead={{ id: 8, nom: 'Test2', stage: 'FOLLOW_UP' }}
        onInlineSave={vi.fn(() => Promise.resolve())}
      />,
    )
    const select = screen.getByLabelText(/Changer l'étape/)
    const byValue = (v) => [...select.options].find((o) => o.value === v)
    expect(byValue('NEW').disabled).toBe(true)
    expect(byValue('CONTACTED').disabled).toBe(true)
    expect(byValue('QUOTE_SENT').disabled).toBe(true)
    expect(byValue('FOLLOW_UP').disabled).toBe(false) // étape courante
    expect(byValue('SIGNED').disabled).toBe(false)
    expect(byValue('COLD').disabled).toBe(false)
  })

  it('LB4 : un lead COLD peut réactiver vers n’importe quelle étape active (bug #7)', () => {
    render(
      <StageMover
        lead={{ id: 9, nom: 'Test3', stage: 'COLD' }}
        onInlineSave={vi.fn(() => Promise.resolve())}
      />,
    )
    const select = screen.getByLabelText(/Changer l'étape/)
    const byValue = (v) => [...select.options].find((o) => o.value === v)
    for (const s of ['NEW', 'CONTACTED', 'QUOTE_SENT', 'FOLLOW_UP', 'SIGNED']) {
      expect(byValue(s).disabled).toBe(false)
    }
  })
})
