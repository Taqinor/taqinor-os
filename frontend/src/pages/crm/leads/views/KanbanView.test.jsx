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

// ORDRE FONDATEUR 2026-08-01 — le StageMover peut désormais faire RECULER un
// lead, sous confirmation (features/crm/confirmRecul, bâti sur ce module).
// `mockConfirmerRecul` est piloté par test : `true` = l'utilisatrice a dit oui.
const mockConfirmerRecul = vi.fn(() => Promise.resolve(true))
vi.mock('../../../../ui/confirm', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
  useConfirmDialog: () => ({ confirm: mockConfirmerRecul, confirmDelete: vi.fn() }),
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
    // 4e argument (ordre fondateur 2026-08-01) : les marqueurs write-only du
    // serializer. Une AVANCÉE n'en porte aucun.
    expect(onInlineSave).toHaveBeenCalledWith(lead, 'stage', 'CONTACTED', { confirmeRecul: false })
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
    await waitFor(() => expect(onInlineSave).toHaveBeenCalledWith(
      lead, 'stage', 'SIGNED', { confirmeRecul: false },
    ))
    // Le select revient honnêtement à l'étape réelle (fini le « Signé ✓
    // Enregistré » fantôme d'un faux Promise.resolve()).
    await waitFor(() =>
      expect(screen.getByLabelText(/Changer l'étape/)).toHaveValue('NEW'))
    expect(toast.error).not.toHaveBeenCalled()
  })

  it("ordre fondateur 2026-08-01 : seule l'étape COURANTE est grisée — reculer est légitime", () => {
    // AVANT (LB4) : reculer était grisé, donc impossible et inexpliqué. Un
    // <option disabled> n'apprend rien à personne. Le garde-fou n'a pas
    // disparu — il est devenu une QUESTION (test suivant).
    render(
      <StageMover
        lead={{ id: 8, nom: 'Test2', stage: 'FOLLOW_UP' }}
        onInlineSave={vi.fn(() => Promise.resolve())}
      />,
    )
    const select = screen.getByLabelText(/Changer l'étape/)
    const byValue = (v) => [...select.options].find((o) => o.value === v)
    for (const s of ['NEW', 'CONTACTED', 'QUOTE_SENT', 'SIGNED', 'COLD']) {
      expect(byValue(s).disabled).toBe(false)
    }
    // La seule option qui ne veut rien dire : l'étape déjà en cours.
    expect(byValue('FOLLOW_UP').disabled).toBe(true)
  })

  it('ordre fondateur 2026-08-01 : un recul CONFIRMÉ enregistre avec le marqueur', async () => {
    const onInlineSave = vi.fn(() => Promise.resolve())
    mockConfirmerRecul.mockResolvedValueOnce(true)
    render(
      <StageMover
        lead={{ id: 10, nom: 'Recul', stage: 'FOLLOW_UP' }}
        onInlineSave={onInlineSave}
      />,
    )
    fireEvent.change(screen.getByLabelText(/Changer l'étape/), {
      target: { value: 'CONTACTED' },
    })
    await waitFor(() => expect(onInlineSave).toHaveBeenCalled())
    // La question a bien été posée, et elle NOMME le lead et les deux étapes.
    expect(mockConfirmerRecul).toHaveBeenCalled()
    expect(mockConfirmerRecul.mock.calls[0][0].title).toContain('Recul')
    expect(mockConfirmerRecul.mock.calls[0][0].title).toContain('Relance')
    expect(mockConfirmerRecul.mock.calls[0][0].title).toContain('Contacté')
    // Le marqueur accompagne l'enregistrement (sans lui le serveur 400).
    expect(onInlineSave).toHaveBeenCalledWith(
      expect.objectContaining({ id: 10 }), 'stage', 'CONTACTED', { confirmeRecul: true },
    )
  })

  it("ordre fondateur 2026-08-01 : un recul ANNULÉ n'enregistre RIEN", async () => {
    const onInlineSave = vi.fn(() => Promise.resolve())
    mockConfirmerRecul.mockResolvedValueOnce(false)
    render(
      <StageMover
        lead={{ id: 11, nom: 'Annulé', stage: 'FOLLOW_UP' }}
        onInlineSave={onInlineSave}
      />,
    )
    fireEvent.change(screen.getByLabelText(/Changer l'étape/), {
      target: { value: 'NEW' },
    })
    await waitFor(() => expect(mockConfirmerRecul).toHaveBeenCalled())
    expect(onInlineSave).not.toHaveBeenCalled()
  })

  it("une AVANCÉE ne pose aucune question et ne porte pas le marqueur", async () => {
    const onInlineSave = vi.fn(() => Promise.resolve())
    render(
      <StageMover
        lead={{ id: 12, nom: 'Avance', stage: 'NEW' }}
        onInlineSave={onInlineSave}
      />,
    )
    fireEvent.change(screen.getByLabelText(/Changer l'étape/), {
      target: { value: 'CONTACTED' },
    })
    await waitFor(() => expect(onInlineSave).toHaveBeenCalled())
    expect(mockConfirmerRecul).not.toHaveBeenCalled()
    expect(onInlineSave).toHaveBeenCalledWith(
      expect.objectContaining({ id: 12 }), 'stage', 'CONTACTED', { confirmeRecul: false },
    )
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
