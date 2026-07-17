// NTUX3/4 — FilterBuilder : groupes ET/OU (2 niveaux max), sélection
// colonne/opérateur, ajout/retrait de condition et de sous-groupe.
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import FilterBuilder from './FilterBuilder'
import { emptyGroup } from './filterLogic'

const COLUMNS = [
  { id: 'statut', header: 'Statut', type: 'select' },
  { id: 'montant', header: 'Montant', type: 'number' },
]

function Harness({ initial = emptyGroup('AND') }) {
  return <StatefulFilterBuilder initial={initial} />
}

// petit wrapper contrôlé — évite de dupliquer un useState dans chaque test.
import { useState } from 'react'
function StatefulFilterBuilder({ initial }) {
  const [value, setValue] = useState(initial)
  return (
    <div>
      <FilterBuilder columns={COLUMNS} value={value} onChange={setValue} />
      <pre data-testid="fb-debug">{JSON.stringify(value)}</pre>
    </div>
  )
}

describe('FilterBuilder (NTUX3)', () => {
  it('rend rien sans colonnes', () => {
    const { container } = render(<FilterBuilder columns={[]} value={emptyGroup()} onChange={() => {}} />)
    expect(container.firstChild).toBeNull()
  })

  it('« + Condition » ajoute une ligne de condition avec le premier champ par défaut', () => {
    render(<Harness />)
    fireEvent.click(screen.getByRole('button', { name: /Condition/ }))
    expect(screen.getAllByTestId('fb-condition-row')).toHaveLength(1)
    expect(screen.getByLabelText('Colonne')).toHaveValue('statut')
  })

  it('« + Groupe (OU) » ajoute un sous-groupe, sans bouton « + Groupe » à l\'intérieur (2 niveaux max)', () => {
    render(<Harness />)
    fireEvent.click(screen.getByRole('button', { name: /Groupe \(OU\)/ }))
    expect(screen.getByTestId('fb-subgroup')).toBeInTheDocument()
    // Un seul bouton "+ Groupe" au total (racine) — aucun à l'intérieur du sous-groupe.
    expect(screen.getAllByRole('button', { name: /Groupe \(OU\)/ })).toHaveLength(1)
  })

  it('changer l\'opérateur ET/OU du groupe racine se reflète dans la valeur', () => {
    render(<Harness />)
    fireEvent.click(screen.getByRole('radio', { name: 'OU' }))
    expect(JSON.parse(screen.getByTestId('fb-debug').textContent).op).toBe('OR')
  })

  it('retirer une condition la fait disparaître', () => {
    render(<Harness />)
    fireEvent.click(screen.getByRole('button', { name: /Condition/ }))
    expect(screen.getAllByTestId('fb-condition-row')).toHaveLength(1)
    fireEvent.click(screen.getByRole('button', { name: 'Retirer cette condition' }))
    expect(screen.queryAllByTestId('fb-condition-row')).toHaveLength(0)
  })

  it('scénario NTUX3 exact : (statut=Envoyé OU statut=Relancé) ET montant>50000', () => {
    render(<Harness />)
    // Racine ET (déjà par défaut) + un sous-groupe OU + une condition montant.
    fireEvent.click(screen.getByRole('button', { name: /Groupe \(OU\)/ }))
    // Deux boutons « + Condition » existent désormais (celui du sous-groupe,
    // rendu EN PREMIER dans le DOM, puis celui de la racine) — on clique
    // celui de la RACINE (le dernier) pour ajouter une condition au niveau 1.
    const conditionButtons = screen.getAllByRole('button', { name: /Condition/ })
    fireEvent.click(conditionButtons[conditionButtons.length - 1])
    const value = JSON.parse(screen.getByTestId('fb-debug').textContent)
    expect(value.op).toBe('AND')
    expect(value.conditions).toHaveLength(2)
    expect(Array.isArray(value.conditions[0].conditions)).toBe(true) // sous-groupe
  })
})
