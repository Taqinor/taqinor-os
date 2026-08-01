import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, screen, cleanup, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'

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

/* ODY26 — l'écran consomme désormais `useInstalledApps()` (ODY1) pour l'axe
   « Applications visibles » : il lui faut donc le store Redux, comme en
   production. Aucun autre changement de rendu. */
function renderPage({ role = 'admin', permissions = [], modulesDesactives = [] } = {}) {
  const store = configureStore({
    reducer: { auth: (s = { role, permissions, modulesDesactives, user: null }) => s },
  })
  return render(
    <Provider store={store}>
      <ThemeProvider>
        <MemoryRouter>
          <ConfirmProvider>
            <RolesManagement />
          </ConfirmProvider>
        </MemoryRouter>
      </ThemeProvider>
    </Provider>,
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

/* ODY26 — « installée pour la société » (ModuleToggle) et « visible pour ce
   rôle » avaient DEUX systèmes sans surface commune. L'axe « Applications
   visibles » les réunit dans la matrice de rôles, sans nouveau champ backend :
   il n'écrit que des permissions `app_<clé>_voir` dans `Role.permissions`. */
describe('RolesManagement — axe « Applications visibles » (ODY26)', () => {
  async function ouvrirFormulaire(user, options) {
    rolesApiMock.getRoles.mockResolvedValue({ data: ROLES })
    renderPage(options)
    await screen.findByText('Commercial')
    await user.click(screen.getByRole('button', { name: /Nouveau rôle/ }))
    return screen.getByTestId('role-apps-axis')
  }

  const casesApps = () =>
    within(screen.getByTestId('role-apps-axis')).getAllByRole('checkbox')

  it('par défaut aucun rôle n’est restreint (comportement historique préservé)', async () => {
    const user = userEvent.setup()
    const axe = await ouvrirFormulaire(user)

    expect(within(axe).getAllByRole('checkbox').length).toBeGreaterThan(1)
    expect(screen.getByText(/Aucune restriction/)).toBeInTheDocument()
    // Rien n'est écrit tant que l'admin n'a rien décoché.
    expect(screen.getByRole('button', { name: 'Toutes les applications' }))
      .toBeDisabled()
  })

  it('décocher une app bascule le rôle en liste blanche (les autres restent visibles)', async () => {
    const user = userEvent.setup()
    await ouvrirFormulaire(user)
    const total = casesApps().length

    await user.click(casesApps()[0])

    expect(await screen.findByText(
      new RegExp(`Ce rôle n.ouvre que ${total - 1} application`),
    )).toBeInTheDocument()
    const apres = casesApps()
    expect(apres[0]).not.toBeChecked()
    expect(apres[1]).toBeChecked()
  })

  it('« Toutes les applications » efface la restriction', async () => {
    const user = userEvent.setup()
    await ouvrirFormulaire(user)

    await user.click(casesApps()[0])
    await screen.findByText(/Ce rôle n.ouvre que/)

    await user.click(screen.getByRole('button', { name: 'Toutes les applications' }))

    expect(await screen.findByText(/Aucune restriction/)).toBeInTheDocument()
    casesApps().forEach(c => expect(c).toBeChecked())
  })

  it('n’expose que les apps INSTALLÉES pour la société (ODX6 respecté)', async () => {
    const user = userEvent.setup()
    await ouvrirFormulaire(user)
    const total = casesApps().length
    cleanup()

    await ouvrirFormulaire(user, { modulesDesactives: ['crm'] })

    expect(casesApps().length).toBe(total - 1)
  })
})
