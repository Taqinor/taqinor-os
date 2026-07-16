import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, screen, cleanup, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

/* VX234 — le dialogue de réassignation (avant suppression d'un rôle assigné)
   listait TOUS les rôles sans tri ni annotation : un clic hâtif pouvait
   réassigner des commerciaux vers « Administrateur » sans avertissement. On
   verrouille : (1) le <Select> trie les rôles par nombre de permissions
   CROISSANT (le moins large en premier) ; (2) un badge « plus large »
   apparaît une fois une cible plus permissive que l'original sélectionnée. */

const { apiMock, rolesApiMock } = vi.hoisted(() => ({
  apiMock: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
  rolesApiMock: {
    getRoles: vi.fn(),
    getPermissionsDisponibles: vi.fn(() => Promise.resolve({ data: { permissions: [] } })),
    deleteRole: vi.fn(),
  },
}))
vi.mock('../../api/axios', () => ({ default: apiMock }))
vi.mock('../../api/rolesApi', () => ({ default: rolesApiMock }))

if (typeof globalThis.ResizeObserver === 'undefined') {
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
}

import RolesManagement from './RolesManagement'
import { ThemeProvider } from '../../design/ThemeProvider'
import { ConfirmProvider } from '../../providers/ConfirmProvider'

const ROLES = [
  {
    id: 1, nom: 'Commercial', est_systeme: false, users_count: 1,
    users: [{ id: 10, username: 'sam' }],
    permissions: ['crm_voir', 'crm_creer'],
  },
  {
    id: 2, nom: 'Administrateur', est_systeme: true, users_count: 0, users: [],
    permissions: ['crm_voir', 'crm_creer', 'crm_supprimer', 'roles_gerer', 'stock_voir'],
  },
  {
    id: 3, nom: 'Lecteur', est_systeme: false, users_count: 0, users: [],
    permissions: ['crm_voir'],
  },
]

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

function renderPage() {
  return render(
    <ThemeProvider>
      <MemoryRouter>
        <ConfirmProvider>
          <RolesManagement />
        </ConfirmProvider>
      </MemoryRouter>
    </ThemeProvider>,
  )
}

describe('RolesManagement (VX234 — dialogue de réassignation)', () => {
  it('trie les rôles cibles par nombre de permissions croissant', async () => {
    rolesApiMock.getRoles.mockResolvedValue({ data: ROLES })
    // deleteRole rejette (rôle assigné) pour ouvrir le dialogue de réassignation.
    rolesApiMock.deleteRole.mockRejectedValue({
      response: { data: { detail: 'Ce rôle est assigné à des utilisateurs.' } },
    })
    const user = userEvent.setup()
    renderPage()

    await screen.findByText('Commercial')
    // VX38 — la suppression vit désormais dans les actions de ligne DataTable
    // (action rapide au survol, IconButton étiqueté par aria-label) : on cible
    // la ligne « Commercial » précisément, comme UsersManagement.test.jsx cible
    // sa ligne par contenu plutôt que par index global de bouton.
    const commercialRow = [...document.querySelectorAll('table tbody tr')]
      .find((tr) => tr.textContent.includes('Commercial'))
    expect(commercialRow).toBeTruthy()
    const rowDeleteBtn = within(commercialRow).getByRole('button', { name: 'Supprimer' })
    await user.click(rowDeleteBtn)

    // Confirmation maison (AlertDialog du ConfirmProvider), JAMAIS window.confirm.
    // On clique « Supprimer » DANS la boîte de dialogue (portée dans le body).
    const confirmBtn = await waitFor(() => {
      const btn = [...document.querySelectorAll('[role="alertdialog"] button')]
        .find((b) => b.textContent.trim() === 'Supprimer')
      expect(btn).toBeTruthy()
      return btn
    })
    await user.click(confirmBtn)

    await waitFor(() => screen.getByText('Réassigner avant de supprimer'))
    const combo = screen.getByRole('combobox')
    await user.click(combo)

    const options = await screen.findAllByRole('option')
    const texts = options.map(o => o.textContent)
    // Lecteur (1 permission) doit précéder Administrateur (5 permissions).
    const idxLecteur = texts.findIndex(t => t.includes('Lecteur'))
    const idxAdmin = texts.findIndex(t => t.includes('Administrateur'))
    expect(idxLecteur).toBeGreaterThanOrEqual(0)
    expect(idxAdmin).toBeGreaterThanOrEqual(0)
    expect(idxLecteur).toBeLessThan(idxAdmin)
    // Administrateur porte l'annotation "plus large" (5 > 2 permissions du rôle original).
    expect(texts[idxAdmin]).toMatch(/plus large/)
    // Lecteur (1 < 2) n'est pas annoté plus large.
    expect(texts[idxLecteur]).not.toMatch(/plus large/)
  })

  it('affiche un badge d\'avertissement quand la cible choisie est plus large', async () => {
    rolesApiMock.getRoles.mockResolvedValue({ data: ROLES })
    rolesApiMock.deleteRole.mockRejectedValue({
      response: { data: { detail: 'Ce rôle est assigné à des utilisateurs.' } },
    })
    const user = userEvent.setup()
    renderPage()

    await screen.findByText('Commercial')
    const commercialRow = [...document.querySelectorAll('table tbody tr')]
      .find((tr) => tr.textContent.includes('Commercial'))
    expect(commercialRow).toBeTruthy()
    const rowDeleteBtn = within(commercialRow).getByRole('button', { name: 'Supprimer' })
    await user.click(rowDeleteBtn)

    const confirmBtn = await waitFor(() => {
      const btn = [...document.querySelectorAll('[role="alertdialog"] button')]
        .find((b) => b.textContent.trim() === 'Supprimer')
      expect(btn).toBeTruthy()
      return btn
    })
    await user.click(confirmBtn)

    await waitFor(() => screen.getByText('Réassigner avant de supprimer'))
    const combo = screen.getByRole('combobox')
    await user.click(combo)
    const adminOption = await screen.findByRole('option', { name: /Administrateur/ })
    await user.click(adminOption)

    expect(await screen.findByText(/plus large que « Commercial »/)).toBeInTheDocument()
  })
})
