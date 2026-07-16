import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { render, screen, within, cleanup, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* J145 — Admin Utilisateurs migré sur le DataTable unifié (cellule avatar,
   pastilles de rôle StatusPill, actions groupées) + édition cohérente en
   ResponsiveDialog (Sheet sur mobile). Ce test verrouille :
   • le rendu DataTable (lignes <tr> + en-têtes connus) ;
   • les contrats e2e (heading, bouton « + Nouvel utilisateur », ligne <tr>
     par utilisateur, action « Modifier », modale .modal « Employé — … » avec
     le champ « Nouveau mot de passe ») ;
   • le flux CRUD/permissions inchangé (création POST /users/, suppression via
     confirmation maison, garde « dernier admin »). */

// ── Mocks réseau : l'API axios + l'API rôles (aucun appel réel) ──
// `vi.hoisted` : les définitions sont remontées avec les `vi.mock`, donc les
// fabriques peuvent y accéder sans erreur d'initialisation.
const { apiMock, rolesApiMock } = vi.hoisted(() => ({
  apiMock: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
  rolesApiMock: { getRoles: vi.fn() },
}))
vi.mock('../../api/axios', () => ({ default: apiMock }))
vi.mock('../../api/rolesApi', () => ({ default: rolesApiMock }))

// useSelector → username courant (sert à masquer la suppression de soi-même).
vi.mock('react-redux', () => ({
  useSelector: (sel) => sel({ auth: { user: { username: 'demo_admin' } } }),
}))

// jsdom n'implémente ni ResizeObserver (utilisé par Radix Dialog/Sheet) ni
// scrollIntoView : on pose des stubs minimaux pour que la modale se monte.
if (typeof globalThis.ResizeObserver === 'undefined') {
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
}
if (typeof window.HTMLElement !== 'undefined' && !window.HTMLElement.prototype.scrollIntoView) {
  window.HTMLElement.prototype.scrollIntoView = () => {}
}

// matchMedia déterministe (ResponsiveDialog s'appuie dessus). Bureau par défaut.
function mockMatchMedia(mobile) {
  window.matchMedia = (query) => ({
    matches: mobile,
    media: query,
    onchange: null,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => false,
  })
}

import { MemoryRouter } from 'react-router-dom'
import UsersManagement from './UsersManagement'
import { ConfirmProvider } from '../../providers/ConfirmProvider'
import { ThemeProvider } from '../../design/ThemeProvider'
import { toast } from '../../ui/confirm'

const ROLES = [
  { id: 1, nom: 'Administrateur', est_systeme: true, permissions: ['roles_gerer'] },
  { id: 2, nom: 'Utilisateur', est_systeme: true, permissions: [] },
]

const USERS = [
  {
    id: 10, username: 'demo_admin', email: 'admin@taqinor.ma', poste: 'Directeur',
    role: 1, role_nom: 'Administrateur', is_active: true, is_superuser: true,
    is_protected: true, permissions: ['roles_gerer'], avatar_url: null,
  },
  {
    id: 11, username: 'sami', email: 'sami@taqinor.ma', poste: 'Commercial',
    role: 2, role_nom: 'Utilisateur', is_active: true, is_superuser: false,
    is_protected: false, permissions: [], avatar_url: null,
  },
]

function renderPage() {
  return render(
    <MemoryRouter>
      <ThemeProvider>
        <ConfirmProvider>
          <UsersManagement />
        </ConfirmProvider>
      </ThemeProvider>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  mockMatchMedia(false)
  apiMock.get.mockReset().mockResolvedValue({ data: USERS })
  apiMock.post.mockReset().mockResolvedValue({ data: {} })
  apiMock.patch.mockReset().mockResolvedValue({ data: {} })
  apiMock.delete.mockReset().mockResolvedValue({ data: {} })
  rolesApiMock.getRoles.mockReset().mockResolvedValue({ data: ROLES })
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('UsersManagement — DataTable (J145)', () => {
  it('affiche le titre et le bouton de création (contrats e2e)', async () => {
    renderPage()
    expect(
      screen.getByRole('heading', { name: 'Gestion des utilisateurs' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: '+ Nouvel utilisateur' }),
    ).toBeInTheDocument()
  })

  it('charge utilisateurs + rôles et rend le DataTable unifié (lignes <tr> + grille)', async () => {
    const { container } = renderPage()
    await waitFor(() => expect(apiMock.get).toHaveBeenCalledWith('/users/'))
    expect(rolesApiMock.getRoles).toHaveBeenCalled()

    // Marqueurs DATATABLE (migration J145) : conteneur + grille ARIA + recherche.
    await screen.findAllByText('sami')
    expect(container.querySelector('[data-dt-table]')).toBeTruthy()
    expect(container.querySelector('table[role="grid"]')).toBeTruthy()
    expect(screen.getByLabelText('Recherche globale')).toBeInTheDocument()

    // Le DataTable rend bien des lignes <tr> (contrat e2e) — une par utilisateur.
    const rows = container.querySelectorAll('table tbody tr')
    expect(rows.length).toBeGreaterThanOrEqual(USERS.length)
    expect(screen.getAllByText('demo_admin').length).toBeGreaterThanOrEqual(1)
  })

  it('rend la pastille de rôle (StatusPill) et la cellule avatar', async () => {
    const { container } = renderPage()
    await screen.findAllByText('sami')
    // Pastilles de rôle visibles.
    expect(screen.getAllByText('Utilisateur').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('Administrateur').length).toBeGreaterThanOrEqual(1)
    // StatusPill : pastille avec point coloré (span aria-hidden rond) — preuve
    // qu'on utilise le primitif de statut unifié, pas un Badge nu.
    expect(container.querySelector('span[aria-hidden="true"].rounded-full')).toBeTruthy()
    // Cellule avatar : un <img> (photo) ou les initiales colorées par défaut.
    // L'Avatar par défaut rend les initiales (title = username).
    expect(container.querySelector('[title="sami"]')).toBeTruthy()
  })

  it('crée un utilisateur via le formulaire (POST /users/, sélecteurs e2e)', async () => {
    renderPage()
    await screen.findAllByText('sami')

    fireEvent.click(screen.getByRole('button', { name: '+ Nouvel utilisateur' }))

    // Le formulaire de création : champ sans type (username), email, password,
    // et le bouton « Créer » exact (contrats e2e).
    const createBtn = screen.getByRole('button', { name: 'Créer' })
    const form = createBtn.closest('form')
    expect(form).toBeTruthy()
    const username = form.querySelector('input:not([type])')
    const email = form.querySelector('input[type="email"]')
    const password = form.querySelector('input[type="password"]')
    expect(username).toBeTruthy()
    expect(email).toBeTruthy()
    expect(password).toBeTruthy()

    fireEvent.change(username, { target: { value: 'nouveau' } })
    fireEvent.change(email, { target: { value: 'nouveau@taqinor.ma' } })
    fireEvent.change(password, { target: { value: 'Az9ployxQ!' } })
    fireEvent.click(createBtn)

    await waitFor(() => expect(apiMock.post).toHaveBeenCalledWith('/users/', expect.objectContaining({
      username: 'nouveau',
      email: 'nouveau@taqinor.ma',
      password: 'Az9ployxQ!',
    })))
  })

  // VX104 — le superviseur se règle dès la création (mêmes options que
  // EquipeSection.jsx) ; sans lien, la hiérarchie était oubliée en silence.
  it('VX104 — règle le superviseur dès la création (POST /users/ avec supervisor)', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findAllByText('sami')

    await user.click(screen.getByRole('button', { name: '+ Nouvel utilisateur' }))
    const createBtn = screen.getByRole('button', { name: 'Créer' })
    const form = createBtn.closest('form')

    fireEvent.change(form.querySelector('input:not([type])'), { target: { value: 'stagiaire' } })
    fireEvent.change(form.querySelector('input[type="password"]'), { target: { value: 'Az9ployxQ!' } })

    // Sélectionne « sami » comme superviseur direct.
    await user.click(within(form).getByRole('combobox', { name: /Superviseur direct/i }))
    await user.click(await screen.findByRole('option', { name: 'sami' }))

    await user.click(createBtn)

    await waitFor(() => expect(apiMock.post).toHaveBeenCalledWith('/users/', expect.objectContaining({
      username: 'stagiaire', supervisor: 11,
    })))
  })

  it('VX104 — création SANS superviseur affiche un toast de rappel avec lien', async () => {
    const messageSpy = vi.spyOn(toast, 'message')
    const user = userEvent.setup()
    renderPage()
    await screen.findAllByText('sami')

    await user.click(screen.getByRole('button', { name: '+ Nouvel utilisateur' }))
    const createBtn = screen.getByRole('button', { name: 'Créer' })
    const form = createBtn.closest('form')

    fireEvent.change(form.querySelector('input:not([type])'), { target: { value: 'sans-sup' } })
    fireEvent.change(form.querySelector('input[type="password"]'), { target: { value: 'Az9ployxQ!' } })
    await user.click(createBtn)

    await waitFor(() => expect(apiMock.post).toHaveBeenCalledWith('/users/', expect.objectContaining({
      username: 'sans-sup', supervisor: null,
    })))
    // Toast de rappel (pas un succès plat) : description explicite + action
    // de lien vers Paramètres → Équipe, où la hiérarchie reste réglable.
    await waitFor(() => expect(messageSpy).toHaveBeenCalledWith('Utilisateur créé.', expect.objectContaining({
      description: 'Pensez à définir son responsable direct.',
      action: expect.objectContaining({ label: 'Paramètres → Équipe' }),
    })))
    messageSpy.mockRestore()
  })

  it('ouvre l\'édition dans une modale .modal « Employé — … » avec « Nouveau mot de passe »', async () => {
    renderPage()
    await screen.findAllByText('sami')

    // Action « Modifier » sur la ligne (rapide ou kebab) → ouvre la ResponsiveDialog.
    const editButtons = screen.getAllByRole('button', { name: 'Modifier' })
    fireEvent.click(editButtons[0])

    // Modale .modal portée dans le body (contrat e2e + viewport mobile).
    const dialog = await waitFor(() => {
      const d = document.querySelector('[role="dialog"].modal')
      expect(d).toBeTruthy()
      return d
    })
    expect(within(dialog).getByText(/Employé — /)).toBeInTheDocument()
    // Champ « Nouveau mot de passe » exact (réinitialisation atteignable).
    expect(within(dialog).getByText('Nouveau mot de passe')).toBeInTheDocument()
    // Input fichier (upload photo) présent dans la modale.
    expect(dialog.querySelector('input[type="file"]')).toBeTruthy()
  })

  it('enregistre l\'édition via PATCH /users/<id>/', async () => {
    renderPage()
    await screen.findAllByText('sami')
    const editButtons = screen.getAllByRole('button', { name: 'Modifier' })
    // La 2e ligne (sami) est éditable sans garde admin.
    fireEvent.click(editButtons[editButtons.length - 1])

    const dialog = await waitFor(() => {
      const d = document.querySelector('[role="dialog"].modal')
      expect(d).toBeTruthy()
      return d
    })
    const save = within(dialog).getByRole('button', { name: 'Enregistrer' })
    fireEvent.click(save)
    await waitFor(() =>
      expect(apiMock.patch).toHaveBeenCalledWith(
        expect.stringMatching(/^\/users\/\d+\/$/),
        expect.any(Object),
      ),
    )
  })

  it('supprime un utilisateur via la confirmation maison (DELETE /users/<id>/)', async () => {
    const user = userEvent.setup()
    const { container } = renderPage()
    await screen.findAllByText('sami')

    // La suppression vit dans le menu kebab « Plus d'actions sur la ligne »
    // (action destructive, séparée) — disponible uniquement pour les comptes
    // non protégés et différents de soi-même → on cible la ligne de « sami ».
    const samiRow = [...container.querySelectorAll('table tbody tr')]
      .find((tr) => tr.textContent.includes('sami'))
    expect(samiRow).toBeTruthy()
    const kebab = within(samiRow).getByRole('button', { name: "Plus d'actions sur la ligne" })
    await user.click(kebab)

    // L'entrée de menu « Supprimer » (role menuitem) déclenche la confirmation.
    const delItem = await screen.findByRole('menuitem', { name: 'Supprimer' })
    await user.click(delItem)

    // Confirmation maison (AlertDialog), JAMAIS window.confirm. On clique
    // « Supprimer » dans la boîte portée dans le body.
    const confirmBtn = await waitFor(() => {
      const btn = [...document.querySelectorAll('[role="alertdialog"] button')]
        .find((b) => b.textContent.trim() === 'Supprimer')
      expect(btn).toBeTruthy()
      return btn
    })
    await user.click(confirmBtn)

    await waitFor(() =>
      expect(apiMock.delete).toHaveBeenCalledWith(expect.stringMatching(/^\/users\/\d+\/$/)),
    )
  })
})
