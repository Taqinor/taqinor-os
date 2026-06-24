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
