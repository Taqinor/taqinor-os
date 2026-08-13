import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import gedApi from '../../api/gedApi'
import GedSearch from './GedSearch.jsx'

// Régression GED13 : l'état vide passait un ÉLÉMENT JSX (`icon={<Inbox/>}`) au
// composant EmptyState, qui attend un TYPE de composant (`const Icon = icon`).
// Résultat : « Element type is invalid » → la page GED plantait dès qu'une
// recherche ne renvoyait aucun résultat. Ce test rend GedSearch, déclenche une
// recherche sans résultat, et vérifie que l'état vide s'affiche sans planter.
vi.mock('../../api/gedApi', () => ({
  default: {
    getTags: vi.fn(() => Promise.resolve({ data: [] })),
    searchDocuments: vi.fn(() => Promise.resolve({ data: [] })),
    semanticSearch: vi.fn(() => Promise.resolve({ data: [] })),
    getDocuments: vi.fn(() => Promise.resolve({ data: [] })),
    // ZGED7/8/13 — favoris, récents, vues enregistrées.
    getMesFavoris: vi.fn(() => Promise.resolve({ data: { dossiers: [], documents: [] } })),
    getMesRecents: vi.fn(() => Promise.resolve({ data: { consultes: [], deposes: [] } })),
    getVues: vi.fn(() => Promise.resolve({ data: [] })),
    createVue: vi.fn(() => Promise.resolve({ data: { id: 1 } })),
    deleteVue: vi.fn(() => Promise.resolve({ data: {} })),
  },
}))

describe('GedSearch — état vide', () => {
  it("affiche l'état vide sans planter quand la recherche ne renvoie aucun résultat", async () => {
    gedApi.searchDocuments.mockResolvedValueOnce({ data: [] })

    render(<GedSearch />)

    await userEvent.type(screen.getByLabelText('Recherche plein-texte'), 'facture')
    await userEvent.click(screen.getByRole('button', { name: /Rechercher/i }))

    expect(await screen.findByText('Aucun résultat')).toBeInTheDocument()
    expect(
      screen.getByText('Aucun document ne correspond à ces critères.'),
    ).toBeInTheDocument()
    expect(gedApi.searchDocuments).toHaveBeenCalledWith({ q: 'facture' })
  })
})

describe('ZGED7/8/13 GedSearch — favoris, récents & vues enregistrées', () => {
  it('liste les favoris et récents personnels, ouvre le document au clic', async () => {
    gedApi.getMesFavoris.mockResolvedValueOnce({
      data: { dossiers: [], documents: [{ id: 8, nom: 'facture.pdf', favori_id: 1 }] },
    })
    gedApi.getMesRecents.mockResolvedValueOnce({
      data: { consultes: [{ id: 9, nom: 'devis.pdf' }], deposes: [] },
    })
    const onOpenDocument = vi.fn()
    render(<GedSearch onOpenDocument={onOpenDocument} />)

    await userEvent.click(await screen.findByText('facture.pdf'))
    expect(onOpenDocument).toHaveBeenCalledWith({ id: 8, nom: 'facture.pdf', favori_id: 1 })

    await userEvent.click(screen.getByText('devis.pdf'))
    expect(onOpenDocument).toHaveBeenCalledWith({ id: 9, nom: 'devis.pdf' })
  })

  it('enregistre la recherche courante comme une vue réutilisable', async () => {
    render(<GedSearch />)
    await userEvent.type(screen.getByLabelText('Recherche plein-texte'), 'facture')

    await userEvent.click(screen.getByRole('button', { name: /Enregistrer/i }))
    await userEvent.type(screen.getByLabelText('Nom de la vue'), 'Mes factures')
    await userEvent.click(screen.getByRole('checkbox', { name: /Partagée/i }))
    const enregistrerButtons = screen.getAllByRole('button', { name: /^Enregistrer$/i })
    await userEvent.click(enregistrerButtons[enregistrerButtons.length - 1])

    expect(gedApi.createVue).toHaveBeenCalledWith({
      nom: 'Mes factures',
      criteres: { query: 'facture', tagId: null, semantic: false },
      partagee: true,
    })
  })

  it('applique une vue enregistrée et relance la recherche', async () => {
    gedApi.getVues.mockResolvedValueOnce({
      data: [{ id: 3, nom: 'Mes factures', criteres: { query: 'facture', tagId: null, semantic: false }, partagee: false }],
    })
    render(<GedSearch />)

    await userEvent.click(await screen.findByText('Mes factures'))
    await vi.waitFor(() => expect(gedApi.searchDocuments).toHaveBeenCalledWith({ q: 'facture' }))
  })

  it('supprime une vue enregistrée', async () => {
    gedApi.getVues.mockResolvedValueOnce({
      data: [{ id: 3, nom: 'Mes factures', criteres: {}, partagee: false }],
    })
    render(<GedSearch />)

    await userEvent.click(await screen.findByRole('button', { name: /Supprimer la vue Mes factures/i }))
    expect(gedApi.deleteVue).toHaveBeenCalledWith(3)
  })
})
