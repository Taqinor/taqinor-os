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
    listBlocs: vi.fn().mockResolvedValue({ data: [] }),
  },
}))

vi.mock('../../api/customFieldsApi', () => ({
  default: { getDefs: vi.fn().mockResolvedValue({ data: [] }) },
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

describe('ArticleEditor — emoji (ZGED10)', () => {
  it('envoie l’emoji saisi à la création', async () => {
    const user = userEvent.setup()
    render(wrap(<ArticleEditor article={null} onCancel={() => {}} onSaved={() => {}} />))
    await user.type(screen.getByLabelText('Titre'), 'Nouvel article')
    await user.type(screen.getByLabelText('Emoji'), '📘')
    await user.click(screen.getByRole('button', { name: /^Enregistrer$/i }))
    expect(kbApi.createArticle).toHaveBeenCalledWith(
      expect.objectContaining({ emoji: '📘' }))
  })
})

describe('ArticleEditor — bloc réutilisable (ZGED12)', () => {
  it('insère le corps du bloc choisi dans le contenu', async () => {
    kbApi.listBlocs.mockResolvedValue({
      data: [{ id: 3, nom: 'Signature standard', corps: 'Cordialement, l’équipe TAQINOR' }],
    })
    const user = userEvent.setup()
    render(wrap(<ArticleEditor article={null} onCancel={() => {}} onSaved={() => {}} />))
    await screen.findByLabelText('Choisir un bloc réutilisable')
    await user.selectOptions(screen.getByLabelText('Choisir un bloc réutilisable'), '3')
    await user.click(screen.getByRole('button', { name: /^Insérer$/i }))
    expect(screen.getByLabelText('Contenu')).toHaveValue('Cordialement, l’équipe TAQINOR')
  })
})
