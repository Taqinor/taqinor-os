import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'
import gedApi from '../../../api/gedApi'
import { toast } from '../../../ui'
import RoutagesPage from './RoutagesPage.jsx'

/* PACT136 — Routage documentaire automatique (ZGED6) : liste source →
   dossier cible avec un aperçu des SEGMENTS (statiques vs jetons `{{ }}`,
   jamais une valeur résolue inventée puisqu'aucun contexte réel n'existe
   côté écran), création, activation. Mocks alignés sur
   `RoutageDocumentaireSerializer` (id, source, cabinet_cible, cabinet_cible_nom,
   dossier_cible, tags_defaut, actif). Comme `CorbeillePage.test.jsx` :
   ListShell rend une vue table + une vue carte, donc toute assertion sur une
   cellule/action de ligne passe par `findAllByText`/`getAllByRole(...)`. */

vi.mock('../../../api/gedApi', () => ({
  default: {
    getRoutagesDocumentaires: vi.fn(),
    getCabinets: vi.fn(() => Promise.resolve({ data: [{ id: 1, nom: 'Paie' }] })),
    getTags: vi.fn(() => Promise.resolve({ data: [{ id: 2, nom: 'Confidentiel', slug: 'confidentiel' }] })),
    createRoutageDocumentaire: vi.fn(() => Promise.resolve({ data: { id: 9 } })),
    updateRoutageDocumentaire: vi.fn(() => Promise.resolve({ data: {} })),
    deleteRoutageDocumentaire: vi.fn(() => Promise.resolve({ data: {} })),
  },
}))

vi.mock('../../../ui', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, toast: { success: vi.fn(), error: vi.fn(), message: vi.fn() } }
})

function renderPage() {
  return render(
    <MemoryRouter><ThemeProvider><RoutagesPage /></ThemeProvider></MemoryRouter>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  gedApi.getRoutagesDocumentaires.mockResolvedValue({
    data: [{
      id: 6, source: 'paie_bulletin', cabinet_cible: 1, cabinet_cible_nom: 'Paie',
      dossier_cible: 'Paie/{{ annee }}', tags_defaut: [2], actif: true,
    }],
  })
})

describe('PACT136 RoutagesPage', () => {
  it('liste les routages avec un aperçu des segments (statique vs jeton)', async () => {
    renderPage()
    expect((await screen.findAllByText('paie_bulletin')).length).toBeGreaterThan(0)
    expect(screen.getAllByText('Paie').length).toBeGreaterThan(0)
    expect(screen.getAllByText('{{ annee }}').length).toBeGreaterThan(0)
  })

  it('crée un routage', async () => {
    renderPage()
    await screen.findAllByText('paie_bulletin')

    await userEvent.click(screen.getAllByRole('button', { name: /Nouveau routage/i })[0])
    const dialog = await screen.findByRole('dialog')
    await userEvent.type(within(dialog).getByLabelText('Source'), 'rh_document')
    await userEvent.click(within(dialog).getByRole('combobox', { name: 'Choisir un cabinet cible' }))
    await userEvent.click(within(await screen.findByRole('listbox')).getByText('Paie'))
    // `userEvent.type` traite `{{` comme l'ÉCHAPPEMENT d'une accolade
    // littérale : taper 'RH/{{ annee }}' produit 'RH/{ annee }}'. Le jeton
    // de gabarit se saisit donc au presse-papier, jamais frappe à frappe.
    const champDossier = within(dialog).getByLabelText('Dossier cible')
    await userEvent.click(champDossier)
    await userEvent.paste('RH/{{ annee }}')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Créer' }))

    await waitFor(() => {
      expect(gedApi.createRoutageDocumentaire).toHaveBeenCalledWith({
        source: 'rh_document', cabinet_cible: '1', dossier_cible: 'RH/{{ annee }}', tags_defaut: [],
      })
      expect(toast.success).toHaveBeenCalledWith('Routage créé.')
    })
  })

  it('désactive un routage actif', async () => {
    renderPage()
    await screen.findAllByText('paie_bulletin')

    await userEvent.click(screen.getAllByRole('button', { name: 'Désactiver' })[0])
    await waitFor(() => {
      expect(gedApi.updateRoutageDocumentaire).toHaveBeenCalledWith(6, { actif: false })
      expect(toast.success).toHaveBeenCalledWith('Routage désactivé.')
    })
  })
})
