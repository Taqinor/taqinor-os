import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'

/* FG87 — base de connaissances SAV : liste + création + édition inline.
   savApi mocké. */

vi.mock('../../api/savApi', () => ({
  default: { getKbArticles: vi.fn(), saveKbArticle: vi.fn() },
}))

import savApi from '../../api/savApi'
import KbArticlesPage from './KbArticlesPage'

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('KbArticlesPage', () => {
  it('affiche la liste des articles', async () => {
    savApi.getKbArticles.mockResolvedValue({
      data: [{ id: 1, titre: 'Erreur E07 onduleur Huawei', corps: 'Redémarrer puis...', categorie: 'Onduleur', tags: ['E07', 'Huawei'] }],
    })
    render(<KbArticlesPage />)
    expect(await screen.findByText('Erreur E07 onduleur Huawei')).toBeInTheDocument()
    expect(screen.getByText('Onduleur')).toBeInTheDocument()
  })

  it('crée un nouvel article', async () => {
    savApi.getKbArticles.mockResolvedValue({ data: [] })
    savApi.saveKbArticle.mockResolvedValue({ data: {} })
    render(<KbArticlesPage />)
    await screen.findByText('Aucun article')
    fireEvent.change(screen.getByPlaceholderText('Titre'), { target: { value: 'Panne string' } })
    fireEvent.change(screen.getByPlaceholderText("Corps de l'article (playbook de résolution)"), {
      target: { value: 'Vérifier les fusibles.' },
    })
    fireEvent.click(screen.getByRole('button', { name: /Ajouter/ }))
    await waitFor(() => expect(savApi.saveKbArticle).toHaveBeenCalledWith(null, expect.objectContaining({
      titre: 'Panne string', corps: 'Vérifier les fusibles.',
    })))
  })

  it('affiche un état vide quand aucun article', async () => {
    savApi.getKbArticles.mockResolvedValue({ data: [] })
    render(<KbArticlesPage />)
    expect(await screen.findByText('Aucun article')).toBeInTheDocument()
  })
})
