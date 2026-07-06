import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* XKB9 — champ Visibilité (workspace/prive/partage) ajouté à l'éditeur ;
   défaut ``workspace`` = comportement historique inchangé. */

vi.mock('../../api/kbApi', () => ({
  default: {
    createArticle: vi.fn().mockResolvedValue({ data: { id: 1, statut: 'brouillon' } }),
    updateArticle: vi.fn(),
    publier: vi.fn(),
  },
}))

import kbApi from '../../api/kbApi'
import ArticleEditor from './ArticleEditor'

function wrap(ui) {
  return (
    <MemoryRouter>
      <ThemeProvider>{ui}</ThemeProvider>
    </MemoryRouter>
  )
}

describe('ArticleEditor — visibilité (XKB9)', () => {
  it('propose workspace/prive/partage, défaut workspace', () => {
    render(wrap(<ArticleEditor article={null} onCancel={() => {}} onSaved={() => {}} />))
    const select = screen.getByLabelText('Visibilité')
    expect(select.value).toBe('workspace')
    expect(screen.getByRole('option', { name: 'Privé' })).toBeTruthy()
    expect(screen.getByRole('option', { name: 'Partagé' })).toBeTruthy()
  })

  it('envoie la visibilité choisie à la création', async () => {
    const user = userEvent.setup()
    render(wrap(<ArticleEditor article={null} onCancel={() => {}} onSaved={() => {}} />))
    await user.type(screen.getByLabelText('Titre'), 'Nouvel article')
    await user.selectOptions(screen.getByLabelText('Visibilité'), 'prive')
    await user.click(screen.getByRole('button', { name: /^Enregistrer$/i }))
    expect(kbApi.createArticle).toHaveBeenCalledWith(
      expect.objectContaining({ visibilite: 'prive' }))
  })
})
