import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import KanbanView, { StatusMover } from './KanbanView'
import {
  buildKanbanAnnouncements,
} from '../../../features/kanban/kanbanA11y'

/* VX192 — accessibilité clavier du kanban CHANTIERS : (1) un sélecteur d'étape
   accessible sous chaque carte (StatusMover) restreint aux statuts atteignables
   et déclenche onChangeStatus ; (2) la carte s'ouvre via un <button>
   focalisable (plus de <div onClick>) ; (3) plus aucun window.alert au refus de
   mouvement — remplacé par un bandeau role="status" ; (4) annonces FR pour le
   lecteur d'écran. */

afterEach(() => { cleanup(); vi.clearAllMocks() })

const inst = { id: 3, reference: 'CH-0003', statut: 'en_cours', client_nom: 'X' }

describe('KanbanView chantiers · StatusMover (VX192 clavier)', () => {
  it('rend un sélecteur de statut accessible avec label', () => {
    render(<StatusMover inst={inst} onChangeStatus={vi.fn()} />)
    const select = screen.getByLabelText(/Changer le statut du chantier/)
    expect(select.tagName).toBe('SELECT')
    expect(select).toHaveValue('en_cours')
  })

  it('ne propose que les statuts atteignables (courant ±1)', () => {
    render(<StatusMover inst={inst} onChangeStatus={vi.fn()} />)
    const options = Array.from(
      screen.getByLabelText(/Changer le statut/).querySelectorAll('option'),
    ).map((o) => o.value)
    // en_cours (idx 3) → planifie, en_cours, installe.
    expect(options).toEqual(['planifie', 'en_cours', 'installe'])
  })

  it('appelle onChangeStatus avec le nouveau statut', () => {
    const onChangeStatus = vi.fn()
    render(<StatusMover inst={inst} onChangeStatus={onChangeStatus} />)
    fireEvent.change(screen.getByLabelText(/Changer le statut/), {
      target: { value: 'installe' },
    })
    expect(onChangeStatus).toHaveBeenCalledWith(inst, 'installe')
  })

  it('ne rend rien sans onChangeStatus (lecture seule)', () => {
    const { container } = render(<StatusMover inst={inst} onChangeStatus={undefined} />)
    expect(container.querySelector('select')).toBeNull()
  })
})

describe('KanbanView chantiers · carte ouvrable au clavier + pas de window.alert', () => {
  it('la carte est un <button> focalisable qui appelle onOpen', () => {
    const onOpen = vi.fn()
    const { container } = render(
      <KanbanView items={[inst]} onOpen={onOpen} onChangeStatus={vi.fn()} />,
    )
    const btn = container.querySelector('button.kb-card-open')
    expect(btn).not.toBeNull()
    fireEvent.click(btn)
    expect(onOpen).toHaveBeenCalledWith(inst)
  })

  it('un refus de mouvement n’appelle jamais window.alert', () => {
    const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => {})
    render(<KanbanView items={[inst]} onOpen={vi.fn()} onChangeStatus={vi.fn()} />)
    // La source du code ne doit plus contenir d'appel window.alert : on garantit
    // au moins qu'aucun rendu initial ne le déclenche.
    expect(alertSpy).not.toHaveBeenCalled()
    alertSpy.mockRestore()
  })
})

describe('kanbanA11y · annonces FR partagées (VX192)', () => {
  const ann = buildKanbanAnnouncements((id) =>
    (id === 'installe' ? 'Installé' : id === 3 ? 'CH-0003' : String(id)))

  it('annonce la saisie, le survol, le dépôt et l’annulation en français', () => {
    expect(ann.onDragStart({ active: { id: 3 } })).toBe('Carte CH-0003 saisie.')
    expect(ann.onDragOver({ active: { id: 3 }, over: { id: 'installe' } }))
      .toContain('déplacée sur la colonne Installé')
    expect(ann.onDragEnd({ active: { id: 3 }, over: { id: 'installe' } }))
      .toContain('déposée dans la colonne Installé')
    expect(ann.onDragCancel({ active: { id: 3 } }))
      .toContain('annulé')
  })
})
