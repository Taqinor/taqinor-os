// NTUX25 — ViewBuilderWizard : wizard 3 étapes (colonnes/ordre → filtres →
// nom/visibilité). Reprend les conventions de FilterBuilder.test.jsx.
import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ViewBuilderWizard from './ViewBuilderWizard'

const COLUMNS = [
  { id: 'reference', header: 'Référence', type: 'text' },
  { id: 'statut', header: 'Statut', type: 'select' },
  { id: 'montant', header: 'Montant', type: 'number' },
]

beforeEach(() => vi.clearAllMocks())
afterEach(() => cleanup())

describe('ViewBuilderWizard (NTUX25)', () => {
  it("affiche l'étape 1 (colonnes) en premier, avec toutes les colonnes visibles par défaut", () => {
    render(<ViewBuilderWizard columns={COLUMNS} ecran="ventes.devis" onCreate={vi.fn()} onCancel={vi.fn()} />)
    expect(screen.getByTestId('vbw-step-columns')).toBeInTheDocument()
    expect(screen.getAllByRole('checkbox')).toHaveLength(3)
    expect(screen.getAllByRole('checkbox').every((cb) => cb.getAttribute('data-state') === 'checked')).toBe(true)
  })

  it('décocher une colonne masque ses boutons de réordonnancement', () => {
    render(<ViewBuilderWizard columns={COLUMNS} ecran="ventes.devis" onCreate={vi.fn()} onCancel={vi.fn()} />)
    expect(screen.getByLabelText('Descendre Référence')).toBeInTheDocument()
    // La 1ère checkbox correspond à "Référence" (ordre initial des colonnes).
    fireEvent.click(screen.getAllByRole('checkbox')[0])
    expect(screen.queryByLabelText('Descendre Référence')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Monter Référence')).not.toBeInTheDocument()
  })

  it('« Suivant » est désactivé si aucune colonne visible, réactivé sinon', () => {
    render(<ViewBuilderWizard columns={COLUMNS} ecran="ventes.devis" onCreate={vi.fn()} onCancel={vi.fn()} />)
    const checkboxes = screen.getAllByRole('checkbox')
    checkboxes.forEach((cb) => fireEvent.click(cb))
    expect(screen.getByRole('button', { name: /Suivant/ })).toBeDisabled()
    fireEvent.click(checkboxes[0])
    expect(screen.getByRole('button', { name: /Suivant/ })).not.toBeDisabled()
  })

  it('« Monter »/« Descendre » réordonnent les colonnes visibles', () => {
    render(<ViewBuilderWizard columns={COLUMNS} ecran="ventes.devis" onCreate={vi.fn()} onCancel={vi.fn()} />)
    const labels = () => screen.getByTestId('vbw-step-columns').querySelectorAll('label')
    expect(labels()[0]).toHaveTextContent('Référence')
    fireEvent.click(screen.getByLabelText('Descendre Référence'))
    expect(labels()[0]).toHaveTextContent('Statut')
    expect(labels()[1]).toHaveTextContent('Référence')
  })

  it('navigue vers l\'étape 2 (filtres, FilterBuilder) puis 3 (nom/visibilité)', () => {
    render(<ViewBuilderWizard columns={COLUMNS} ecran="ventes.devis" onCreate={vi.fn()} onCancel={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: /Suivant/ }))
    expect(screen.getByTestId('vbw-step-filters')).toBeInTheDocument()
    expect(screen.getByTestId('filter-builder')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Suivant/ }))
    expect(screen.getByTestId('vbw-step-name')).toBeInTheDocument()
  })

  it('la visibilité "équipe" n\'apparaît que si canShareTeam est vrai', () => {
    render(<ViewBuilderWizard columns={COLUMNS} ecran="ventes.devis" onCreate={vi.fn()} onCancel={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: /Suivant/ }))
    fireEvent.click(screen.getByRole('button', { name: /Suivant/ }))
    expect(screen.queryByText("Partagée à l'équipe")).not.toBeInTheDocument()
    cleanup()

    render(
      <ViewBuilderWizard columns={COLUMNS} ecran="ventes.devis" canShareTeam onCreate={vi.fn()} onCancel={vi.fn()} />,
    )
    fireEvent.click(screen.getByRole('button', { name: /Suivant/ }))
    fireEvent.click(screen.getByRole('button', { name: /Suivant/ }))
    expect(screen.getByText("Partagée à l'équipe")).toBeInTheDocument()
  })

  it("« Créer la vue » appelle onCreate avec ecran/nom/visibilité/configuration en moins de 5 clics", async () => {
    const user = userEvent.setup()
    const onCreate = vi.fn().mockResolvedValue({ id: 1 })
    render(<ViewBuilderWizard columns={COLUMNS} ecran="ventes.devis" onCreate={onCreate} onCancel={vi.fn()} />)

    // 1 clic : Suivant (étape 1 → 2, colonnes par défaut conservées)
    await user.click(screen.getByRole('button', { name: /Suivant/ }))
    // 2e clic : ajouter une condition de filtre (statut en retard)
    await user.click(screen.getByRole('button', { name: /Condition/ }))
    // 3e clic : Suivant (étape 2 → 3)
    await user.click(screen.getByRole('button', { name: /Suivant/ }))
    await user.type(screen.getByLabelText(/Nom de la vue/), 'Mes devis en retard ce mois')
    // 4e clic : Créer la vue
    await user.click(screen.getByRole('button', { name: /Créer la vue/ }))

    await waitFor(() => expect(onCreate).toHaveBeenCalledTimes(1))
    const payload = onCreate.mock.calls[0][0]
    expect(payload.ecran).toBe('ventes.devis')
    expect(payload.nom).toBe('Mes devis en retard ce mois')
    expect(payload.visibilite).toBe('PERSONNELLE')
    expect(payload.configuration.colonnes_visibles).toEqual(['reference', 'statut', 'montant'])
    expect(payload.configuration.filtres.conditions).toHaveLength(1)
  })

  it("« Créer la vue » est désactivé tant qu'aucun nom n'est saisi", () => {
    render(<ViewBuilderWizard columns={COLUMNS} ecran="ventes.devis" onCreate={vi.fn()} onCancel={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: /Suivant/ }))
    fireEvent.click(screen.getByRole('button', { name: /Suivant/ }))
    expect(screen.getByRole('button', { name: /Créer la vue/ })).toBeDisabled()
  })

  it('un échec de création affiche une erreur et ne bloque pas de nouvel essai', async () => {
    const user = userEvent.setup()
    const onCreate = vi.fn().mockRejectedValue(new Error('boom'))
    render(<ViewBuilderWizard columns={COLUMNS} ecran="ventes.devis" onCreate={onCreate} onCancel={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: /Suivant/ }))
    fireEvent.click(screen.getByRole('button', { name: /Suivant/ }))
    await user.type(screen.getByLabelText(/Nom de la vue/), 'Vue test')
    await user.click(screen.getByRole('button', { name: /Créer la vue/ }))
    expect(await screen.findByText('Création de la vue impossible.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Créer la vue/ })).not.toBeDisabled()
  })

  it('« Annuler » appelle onCancel', () => {
    const onCancel = vi.fn()
    render(<ViewBuilderWizard columns={COLUMNS} ecran="ventes.devis" onCreate={vi.fn()} onCancel={onCancel} />)
    fireEvent.click(screen.getByRole('button', { name: 'Annuler' }))
    expect(onCancel).toHaveBeenCalled()
  })
})
