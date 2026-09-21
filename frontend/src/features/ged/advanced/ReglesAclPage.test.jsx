import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'
import gedApi from '../../../api/gedApi'
import rolesApi from '../../../api/rolesApi'
import { toast } from '../../../ui'
import ReglesAclPage from './ReglesAclPage.jsx'

/* PACT133 — Règles d'accès par métadonnée (XGED21) : condition simple
   champ/valeur, rôle cible (jamais un utilisateur nommé), niveau, priorité,
   activables. Mocks alignés sur `RegleAclMetadonneeSerializer` (id, nom,
   condition_group, role, role_nom, niveau, priorite, actif). Comme
   `CorbeillePage.test.jsx` : ListShell rend une vue table + une vue carte,
   donc toute assertion sur une cellule/action de ligne passe par
   `findAllByText`/`getAllByRole(...)`. */

vi.mock('../../../api/gedApi', () => ({
  default: {
    getReglesAclMetadonnee: vi.fn(),
    createRegleAclMetadonnee: vi.fn(() => Promise.resolve({ data: { id: 9 } })),
    updateRegleAclMetadonnee: vi.fn(() => Promise.resolve({ data: {} })),
    deleteRegleAclMetadonnee: vi.fn(() => Promise.resolve({ data: {} })),
  },
}))

vi.mock('../../../api/rolesApi', () => ({
  default: {
    getRoles: vi.fn(() => Promise.resolve({ data: [{ id: 7, nom: 'Commercial' }] })),
  },
}))

vi.mock('../../../ui', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, toast: { success: vi.fn(), error: vi.fn(), message: vi.fn() } }
})

function renderPage() {
  return render(
    <MemoryRouter><ThemeProvider><ReglesAclPage /></ThemeProvider></MemoryRouter>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  gedApi.getReglesAclMetadonnee.mockResolvedValue({
    data: [{
      id: 4, nom: 'Contrats confidentiels', role: 7, role_nom: 'Commercial',
      condition_group: { op: 'and', conditions: [{ field: 'tags', operator: 'contains', value: 'confidentiel' }] },
      niveau: 'lecture', priorite: 5, actif: true,
    }],
  })
  rolesApi.getRoles.mockResolvedValue({ data: [{ id: 7, nom: 'Commercial' }] })
})

describe('PACT133 ReglesAclPage', () => {
  it('liste les règles avec condition, rôle, niveau et priorité', async () => {
    renderPage()
    expect((await screen.findAllByText('Contrats confidentiels')).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/tags contient confidentiel/).length).toBeGreaterThan(0)
    expect(screen.getAllByText('Commercial').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Lecture').length).toBeGreaterThan(0)
  })

  it('crée une règle ACL par métadonnée pour un rôle', async () => {
    renderPage()
    await screen.findAllByText('Contrats confidentiels')

    await userEvent.click(screen.getAllByRole('button', { name: /Nouvelle règle/i })[0])
    const dialog = await screen.findByRole('dialog')
    await userEvent.type(within(dialog).getByLabelText('Nom de la règle'), 'Devis sensibles')
    await userEvent.type(within(dialog).getByLabelText('Champ de la condition'), 'type')
    await userEvent.type(within(dialog).getByLabelText('Valeur de la condition'), 'devis')
    await userEvent.click(within(dialog).getByRole('combobox', { name: 'Choisir un rôle cible' }))
    await userEvent.click(within(await screen.findByRole('listbox')).getByText('Commercial'))
    await userEvent.click(within(dialog).getByRole('button', { name: 'Créer' }))

    await waitFor(() => {
      expect(gedApi.createRegleAclMetadonnee).toHaveBeenCalledWith({
        nom: 'Devis sensibles',
        condition_group: { op: 'and', conditions: [{ field: 'type', operator: 'eq', value: 'devis' }] },
        role: '7',
        niveau: 'lecture',
        priorite: 0,
      })
      expect(toast.success).toHaveBeenCalledWith('Règle créée.')
    })
  })

  it('désactive une règle active', async () => {
    renderPage()
    await screen.findAllByText('Contrats confidentiels')

    await userEvent.click(screen.getAllByRole('button', { name: 'Désactiver' })[0])
    await waitFor(() => {
      expect(gedApi.updateRegleAclMetadonnee).toHaveBeenCalledWith(4, { actif: false })
      expect(toast.success).toHaveBeenCalledWith('Règle désactivée.')
    })
  })
})
