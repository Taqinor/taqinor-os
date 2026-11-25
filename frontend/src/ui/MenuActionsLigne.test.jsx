// T4-X6-005 — le menu « Plus d'actions » d'une ligne de liste (17 actions sur
// la liste des devis) reste DANS la fenêtre : marge de collision, hauteur
// bornée à la place disponible que Radix calcule, défilement interne. Le
// composant est partagé par toutes les listes : la règle vit ici, une fois.
// Nouveau fichier car : le composant n'avait aucun module de test.
//
// Run : npx vitest run src/ui/MenuActionsLigne.test.jsx
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import MenuActionsLigne from './MenuActionsLigne'
import { DropdownMenuItem } from './DropdownMenu'

describe('T4-X6-005 — MenuActionsLigne tient dans la fenêtre', () => {
  it('le contenu est borné à la hauteur disponible et défile', async () => {
    render(
      <MenuActionsLigne declencheur={<button type="button">Plus d'actions</button>}>
        {Array.from({ length: 17 }, (_, i) => (
          <DropdownMenuItem key={i}>Action {i + 1}</DropdownMenuItem>
        ))}
      </MenuActionsLigne>,
    )
    await userEvent.click(screen.getByRole('button', { name: "Plus d'actions" }))
    const menu = await screen.findByRole('menu')
    expect(menu.className).toContain('max-h-[var(--radix-dropdown-menu-content-available-height)]')
    expect(menu.className).toContain('overflow-y-auto')
    expect(screen.getAllByRole('menuitem')).toHaveLength(17)
  })
})
