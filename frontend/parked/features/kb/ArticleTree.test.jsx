import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* XKB8 — panneau d'arbre des articles, replié par défaut, charge l'arbre
   (kbApi.arbre) uniquement à l'ouverture. */

vi.mock('../../api/kbApi', () => ({
  default: { arbre: vi.fn() },
}))

import kbApi from '../../api/kbApi'
import ArticleTree from './ArticleTree'

function wrap(ui) {
  return (
    <MemoryRouter>
      <ThemeProvider>{ui}</ThemeProvider>
    </MemoryRouter>
  )
}

describe('ArticleTree (XKB8)', () => {
  it('ne charge pas l’arbre tant que le panneau est replié', () => {
    render(wrap(<ArticleTree onSelect={() => {}} />))
    expect(kbApi.arbre).not.toHaveBeenCalled()
  })

  it('charge et affiche l’arbre à l’ouverture, sélectionne un nœud au clic', async () => {
    kbApi.arbre.mockResolvedValue({
      data: [
        { id: 1, titre: 'Racine', statut: 'publie', parent: null, ordre: 0, enfants: [
          { id: 2, titre: 'Enfant', statut: 'brouillon', parent: 1, ordre: 0, enfants: [] },
        ] },
      ],
    })
    const onSelect = vi.fn()
    const user = userEvent.setup()
    render(wrap(<ArticleTree onSelect={onSelect} />))

    await user.click(screen.getByRole('button', { name: /Arborescence des articles/i }))
    await waitFor(() => expect(kbApi.arbre).toHaveBeenCalled())
    await waitFor(() => expect(screen.getByText('Racine')).toBeTruthy())

    await user.click(screen.getByText('Racine'))
    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ id: 1, titre: 'Racine' }))
  })
})
