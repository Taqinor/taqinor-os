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
    // WIR226 — les deux wrappers qui existaient depuis toujours et que
    // l'écran n'appelait JAMAIS (il était Create + Read only).
    patchListePrix: vi.fn(),
    deleteListePrix: vi.fn(),
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


/* WIR226 — L'écran était Create + Read only (nom + devise) malgré la ligne
   FE-XSAL1-3 du FRONTEND_GAP_PLAN qui annonçait un « CRUD » : ni renommage, ni
   dates, ni segment, ni archivage, ni suppression — alors que `patchListePrix`
   et `deleteListePrix` existaient depuis toujours des DEUX côtés. Une liste
   devenue fausse restait donc dans la résolution de prix pour toujours. */
describe('ListesPrixPage — WIR226 : CRUD complet', () => {
  const LISTE = {
    id: 1, nom: 'Revendeur', devise: 'MAD', archived: false,
    segment_client: '', date_debut: null, date_fin: null,
    lignes: [], regles: [],
  }

  const ouvrirDetail = async (liste = LISTE) => {
    ventesApi.getListesPrix.mockResolvedValue({ data: [liste] })
    ventesApi.getListePrix.mockResolvedValue({ data: liste })
    render(<ListesPrixPage />)
    fireEvent.click(await screen.findByText(liste.nom))
    return screen.findByRole('dialog')
  }

  it('renomme, cible un segment et date la liste (PATCH réel)', async () => {
    ventesApi.patchListePrix.mockResolvedValue({ data: {} })
    const dialog = await ouvrirDetail()
    fireEvent.change(within(dialog).getByLabelText(/^Nom/),
      { target: { value: 'Revendeur Nord' } })
    fireEvent.change(within(dialog).getByLabelText('Segment client ciblé'),
      { target: { value: 'revendeur' } })
    fireEvent.change(within(dialog).getByLabelText('Valide jusqu’au'),
      { target: { value: '2026-12-31' } })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Enregistrer les modifications' }))

    await waitFor(() => expect(ventesApi.patchListePrix).toHaveBeenCalledWith(1, {
      nom: 'Revendeur Nord',
      devise: 'MAD',
      segment_client: 'revendeur',
      date_debut: null,
      date_fin: '2026-12-31',
    }))
    // Le rechargement suit : la valeur persiste au lieu de vivre dans l'écran.
    await waitFor(() => expect(ventesApi.getListePrix).toHaveBeenCalledWith(1))
  })

  it('archive une liste active (elle sort de la résolution de prix)', async () => {
    ventesApi.patchListePrix.mockResolvedValue({ data: {} })
    const dialog = await ouvrirDetail()
    fireEvent.click(within(dialog).getByRole('button', { name: 'Archiver' }))
    await waitFor(() => expect(ventesApi.patchListePrix)
      .toHaveBeenCalledWith(1, { archived: true }))
  })

  it('réactive une liste archivée', async () => {
    ventesApi.patchListePrix.mockResolvedValue({ data: {} })
    const dialog = await ouvrirDetail({ ...LISTE, nom: 'Ancienne', archived: true })
    expect(within(dialog).getByText(/exclue de la résolution de prix/)).toBeInTheDocument()
    fireEvent.click(within(dialog).getByRole('button', { name: 'Réactiver' }))
    await waitFor(() => expect(ventesApi.patchListePrix)
      .toHaveBeenCalledWith(1, { archived: false }))
  })

  it('la suppression est CONFIRMÉE avant d’appeler le serveur', async () => {
    ventesApi.deleteListePrix.mockResolvedValue({ data: {} })
    const dialog = await ouvrirDetail()
    fireEvent.click(within(dialog).getByRole('button', { name: 'Supprimer' }))
    // Rien n'est encore parti : la confirmation s'ouvre d'abord.
    expect(ventesApi.deleteListePrix).not.toHaveBeenCalled()
    const confirmation = await screen.findByText(/Supprimer « Revendeur » \?/)
    expect(confirmation).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Supprimer définitivement' }))
    await waitFor(() => expect(ventesApi.deleteListePrix).toHaveBeenCalledWith(1))
    // Le détail se ferme et la liste est rechargée (la liste supprimée
    // disparaît alors aussi du sélecteur de la fiche client, qui lit la même
    // ressource).
    await waitFor(() => expect(ventesApi.getListesPrix.mock.calls.length)
      .toBeGreaterThan(1))
  })

  it('un refus serveur est affiché tel quel', async () => {
    ventesApi.patchListePrix.mockRejectedValue({
      response: { data: { detail: 'Une liste porte déjà ce nom.' } },
    })
    const dialog = await ouvrirDetail()
    fireEvent.click(within(dialog).getByRole('button', { name: 'Enregistrer les modifications' }))
    expect(await screen.findByText('Une liste porte déjà ce nom.')).toBeInTheDocument()
  })

  it('la création accepte aussi segment et dates, sans champ vide envoyé', async () => {
    ventesApi.getListesPrix.mockResolvedValue({ data: [] })
    ventesApi.createListePrix.mockResolvedValue({ data: { id: 2 } })
    render(<ListesPrixPage />)
    await screen.findByText('Aucune liste de prix')
    fireEvent.click(screen.getByRole('button', { name: /Nouvelle liste/ }))
    const dialog = await screen.findByRole('dialog')
    fireEvent.change(within(dialog).getByLabelText(/^Nom/), { target: { value: 'Export' } })
    fireEvent.change(within(dialog).getByLabelText('Segment client ciblé'),
      { target: { value: 'export' } })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Créer' }))
    await waitFor(() => expect(ventesApi.createListePrix).toHaveBeenCalledWith({
      nom: 'Export', devise: 'MAD', segment_client: 'export',
    }))
  })
})
