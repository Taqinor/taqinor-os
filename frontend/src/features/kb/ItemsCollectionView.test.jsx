import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

vi.mock('../../api/kbApi', () => ({
  default: { items: vi.fn() },
}))
vi.mock('../../api/customFieldsApi', () => ({
  default: { getDefs: vi.fn().mockResolvedValue({ data: [{ code: 'statut_projet', libelle: 'Statut', actif: true }] }) },
}))

import kbApi from '../../api/kbApi'
import ItemsCollectionView from './ItemsCollectionView'

function wrap(ui) {
  return <MemoryRouter><ThemeProvider>{ui}</ThemeProvider></MemoryRouter>
}

describe('ItemsCollectionView (ZGED11)', () => {
  it('vue liste : affiche les sous-articles avec leurs propriétés', async () => {
    kbApi.items.mockResolvedValue({
      data: [{ id: 1, titre: 'Étape 1', proprietes: { statut_projet: 'En cours' } }],
    })
    render(wrap(<ItemsCollectionView articleId={9} onSelect={() => {}} />))
    await waitFor(() => expect(kbApi.items).toHaveBeenCalledWith(9, { vue: 'liste' }))
    await waitFor(() => expect(screen.getByText('Étape 1')).toBeTruthy())
    expect(screen.getByText('statut_projet: En cours')).toBeTruthy()
  })

  it('sélectionne un item au clic', async () => {
    kbApi.items.mockResolvedValue({ data: [{ id: 5, titre: 'Détail', proprietes: {} }] })
    const onSelect = vi.fn()
    const user = userEvent.setup()
    render(wrap(<ItemsCollectionView articleId={9} onSelect={onSelect} />))
    await waitFor(() => expect(screen.getByText('Détail')).toBeTruthy())
    await user.click(screen.getByText('Détail'))
    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ id: 5 }))
  })

  it('vue kanban : regroupe par propriété choisie', async () => {
    kbApi.items.mockResolvedValue({ data: [] })
    const user = userEvent.setup()
    render(wrap(<ItemsCollectionView articleId={9} onSelect={() => {}} />))
    await waitFor(() => expect(screen.getByLabelText('Type de vue')).toBeTruthy())

    kbApi.items.mockResolvedValue({
      data: { 'En cours': [{ id: 1, titre: 'A', proprietes: {} }], __aucune__: [{ id: 2, titre: 'B', proprietes: {} }] },
    })
    await user.selectOptions(screen.getByLabelText('Type de vue'), 'kanban')
    await waitFor(() => expect(screen.getByLabelText('Propriété de regroupement')).toBeTruthy())
    await user.selectOptions(screen.getByLabelText('Propriété de regroupement'), 'statut_projet')

    await waitFor(() => expect(kbApi.items).toHaveBeenCalledWith(
      9, { vue: 'kanban', propriete: 'statut_projet' }))
    await waitFor(() => expect(screen.getByText('En cours')).toBeTruthy())
    expect(screen.getByText('Sans valeur')).toBeTruthy()
  })

  it('dégrade proprement sans sous-articles', async () => {
    kbApi.items.mockResolvedValue({ data: [] })
    render(wrap(<ItemsCollectionView articleId={9} onSelect={() => {}} />))
    await waitFor(() => expect(screen.getByText('Aucun sous-article')).toBeTruthy())
  })
})
