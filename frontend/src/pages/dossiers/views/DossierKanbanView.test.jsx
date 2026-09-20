import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, within } from '@testing-library/react'
import DossierKanbanView from './DossierKanbanView'

const AUJOURD_HUI = '2026-09-20'

const ITEMS = [
  {
    id: 1, titre: 'Réclamation client X', type_dossier_label: 'Réclamation complexe',
    statut: 'ouvert', priorite: 'critique', priorite_label: 'Critique',
    proprietaire_username: 'meryem', echeance: '2020-01-01',
  },
  {
    id: 2, titre: 'Onboarding Acme', type_dossier_label: 'Onboarding grand compte',
    statut: 'en_cours', priorite: 'normale', priorite_label: 'Normale',
    proprietaire_username: 'reda', echeance: null,
  },
]

describe('DossierKanbanView (NTWFL21)', () => {
  it('range chaque dossier dans la colonne de son statut', () => {
    render(<DossierKanbanView items={ITEMS} aujourdHui={AUJOURD_HUI} />)
    const colOuvert = screen.getByText('Ouvert').closest('section')
    const colEnCours = screen.getByText('En cours').closest('section')
    expect(within(colOuvert).getByText('Réclamation client X')).toBeInTheDocument()
    expect(within(colEnCours).getByText('Onboarding Acme')).toBeInTheDocument()
  })

  it('affiche le badge « en retard » seulement pour l’échéance dépassée', () => {
    render(<DossierKanbanView items={ITEMS} aujourdHui={AUJOURD_HUI} />)
    expect(screen.getByText('En retard')).toBeInTheDocument()
    expect(screen.getAllByText('En retard')).toHaveLength(1)
  })

  it('ouvre la fiche au clic sur une carte', () => {
    const onOpen = vi.fn()
    render(<DossierKanbanView items={ITEMS} aujourdHui={AUJOURD_HUI} onOpen={onOpen} />)
    fireEvent.click(screen.getByText('Réclamation client X'))
    expect(onOpen).toHaveBeenCalledWith(expect.objectContaining({ id: 1 }))
  })

  it('change le statut via le sélecteur clavier (alternative au glisser-déposer)', () => {
    const onChangeStatus = vi.fn()
    render(<DossierKanbanView items={ITEMS} aujourdHui={AUJOURD_HUI} onChangeStatus={onChangeStatus} />)
    const select = screen.getByLabelText('Changer le statut du dossier Réclamation client X')
    fireEvent.change(select, { target: { value: 'clos' } })
    expect(onChangeStatus).toHaveBeenCalledWith(expect.objectContaining({ id: 1 }), 'clos')
  })

  it('n’exige aucune adjacence — n’importe quelle colonne cible est acceptée', () => {
    // NTWFL21 : à la différence du funnel commercial/chantier, le statut
    // d'un dossier n'est pas séquentiel — le sélecteur propose TOUTES les
    // autres valeurs, jamais seulement les voisines.
    render(<DossierKanbanView items={ITEMS} aujourdHui={AUJOURD_HUI} onChangeStatus={vi.fn()} />)
    const select = screen.getByLabelText('Changer le statut du dossier Réclamation client X')
    const values = within(select).getAllByRole('option').map((o) => o.value)
    expect(values).toEqual(['ouvert', 'en_cours', 'en_attente', 'clos', 'abandonne'])
  })
})
