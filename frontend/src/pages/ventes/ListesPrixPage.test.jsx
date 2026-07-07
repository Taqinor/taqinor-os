// XSAL1-2 — écran d'administration des listes de prix (CRUD + lignes/règles).
// Écriture réservée Responsable/Admin côté serveur (ListePrixViewSet) — cet
// écran appelle juste l'API, la garde serveur reste la seule qui compte.

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'

// Radix Select ne s'ouvre pas de façon fiable sous jsdom (portail + pointer
// events) — pattern établi (pages/monitoring/ClientPortalPage.test.jsx) :
// remplacer les primitives Select par un <select> natif pour piloter le choix
// en test, le reste de `../../ui` reste réel.
vi.mock('../../ui', async (importActual) => {
  const actual = await importActual()
  const Passthrough = ({ children }) => <>{children}</>
  return {
    ...actual,
    Select: ({ value, onValueChange, children }) => (
      <select
        role="combobox"
        value={value}
        onChange={(e) => onValueChange(e.target.value)}
      >
        <option value="" />
        {children}
      </select>
    ),
    SelectTrigger: Passthrough,
    SelectValue: () => null,
    SelectContent: Passthrough,
    SelectItem: ({ value, children }) => <option value={value}>{children}</option>,
  }
})

vi.mock('../../api/ventesApi', () => ({
  default: {
    getListesPrix: vi.fn(),
    getListePrix: vi.fn(),
    createListePrix: vi.fn(),
    setLignePrixListe: vi.fn(),
    addRegleListePrix: vi.fn(),
  },
}))
vi.mock('../../api/stockApi', () => ({
  default: { getProduits: vi.fn(() => Promise.resolve({ data: [] })) },
}))

import ventesApi from '../../api/ventesApi'
import stockApi from '../../api/stockApi'
import ListesPrixPage from './ListesPrixPage'

beforeEach(() => {
  vi.clearAllMocks()
  stockApi.getProduits.mockResolvedValue({
    data: [{ id: 1, nom: 'Panneau Solaire 550W', prix_vente: 900 }],
  })
})

describe('ListesPrixPage', () => {
  it('affiche les listes de prix existantes', async () => {
    ventesApi.getListesPrix.mockResolvedValue({
      data: [{ id: 1, nom: 'Revendeur', devise: 'MAD', archived: false, lignes: [], regles: [] }],
    })
    render(<ListesPrixPage />)
    expect(await screen.findByText('Revendeur')).toBeInTheDocument()
  })

  it('état vide quand aucune liste', async () => {
    ventesApi.getListesPrix.mockResolvedValue({ data: [] })
    render(<ListesPrixPage />)
    expect(await screen.findByText('Aucune liste de prix')).toBeInTheDocument()
  })

  it('crée une nouvelle liste via le dialogue', async () => {
    ventesApi.getListesPrix.mockResolvedValue({ data: [] })
    ventesApi.createListePrix.mockResolvedValue({ data: { id: 2, nom: 'Export' } })
    render(<ListesPrixPage />)
    await screen.findByText('Aucune liste de prix')
    fireEvent.click(screen.getByRole('button', { name: /Nouvelle liste/ }))
    const dialog = await screen.findByRole('dialog')
    fireEvent.change(within(dialog).getByLabelText(/Nom/), { target: { value: 'Export' } })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Créer' }))
    await waitFor(() => expect(ventesApi.createListePrix).toHaveBeenCalledWith({ nom: 'Export', devise: 'MAD' }))
  })

  it('ouvre le détail et ajoute un prix fixé', async () => {
    const liste = { id: 1, nom: 'Revendeur', devise: 'MAD', archived: false, lignes: [], regles: [] }
    ventesApi.getListesPrix.mockResolvedValue({ data: [liste] })
    ventesApi.getListePrix.mockResolvedValue({ data: liste })
    ventesApi.setLignePrixListe.mockResolvedValue({ data: { id: 5, produit: 1, prix_unitaire: '850.00' } })
    render(<ListesPrixPage />)
    fireEvent.click(await screen.findByText('Revendeur'))
    const dialog = await screen.findByRole('dialog')
    fireEvent.click(within(dialog).getByRole('button', { name: /Ajouter un prix/ }))
    const addDialogs = await screen.findAllByRole('dialog')
    const addDialog = addDialogs[addDialogs.length - 1]
    const produitSelect = within(addDialog).getByRole('combobox')
    fireEvent.change(produitSelect, { target: { value: '1' } })
    fireEvent.change(within(addDialog).getByLabelText(/Prix unitaire/), { target: { value: '850' } })
    fireEvent.click(within(addDialog).getByRole('button', { name: 'Enregistrer' }))
    await waitFor(() => expect(ventesApi.setLignePrixListe).toHaveBeenCalledWith(
      1, { produit: '1', prix_unitaire: '850' }))
  })
})
