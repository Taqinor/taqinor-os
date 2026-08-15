import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
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
    // WIR250 — création/suppression d'un bloc réutilisable depuis l'éditeur.
    createBloc: vi.fn().mockResolvedValue({ data: { id: 7, nom: 'Mentions' } }),
    removeBloc: vi.fn().mockResolvedValue({ data: {} }),
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

/* WIR250 — ZGED12 était invisible PAR CONSTRUCTION : le sélecteur de blocs
   faisait `return null` quand il n'y avait aucun bloc, et RIEN dans l'app n'en
   créait — donc il ne réapparaissait jamais. L'éditeur porte désormais le seul
   chemin de création (« Enregistrer la sélection comme bloc ») et la barre
   reste rendue même à vide. */
describe('ArticleEditor — création de bloc réutilisable (WIR250)', () => {
  it('la barre de blocs reste visible même sans aucun bloc', async () => {
    kbApi.listBlocs.mockResolvedValue({ data: [] })
    render(wrap(<ArticleEditor article={null} onCancel={() => {}} onSaved={() => {}} />))
    expect(await screen.findByRole('button', {
      name: /Enregistrer la sélection comme bloc/i,
    })).toBeTruthy()
  })

  it('refuse une sélection vide, puis enregistre la sélection', async () => {
    kbApi.listBlocs.mockResolvedValue({ data: [] })
    const user = userEvent.setup()
    render(wrap(<ArticleEditor article={null} onCancel={() => {}} onSaved={() => {}} />))

    const bouton = await screen.findByRole('button', {
      name: /Enregistrer la sélection comme bloc/i,
    })
    // Sélection vide → aucun appel serveur.
    await user.click(bouton)
    expect(kbApi.createBloc).not.toHaveBeenCalled()

    await user.type(screen.getByPlaceholderText('Nom du bloc (optionnel)'), 'Salutation')
    const contenu = screen.getByLabelText('Contenu')
    await user.type(contenu, 'Bonjour tout le monde')
    contenu.setSelectionRange(0, 7)

    await user.click(bouton)
    await waitFor(() => expect(kbApi.createBloc).toHaveBeenCalledWith({
      nom: 'Salutation', corps: 'Bonjour', portee: 'societe',
    }))
  })

  it('supprime le bloc sélectionné', async () => {
    kbApi.listBlocs.mockResolvedValue({
      data: [{ id: 3, nom: 'Signature standard', corps: 'Cordialement' }],
    })
    const user = userEvent.setup()
    render(wrap(<ArticleEditor article={null} onCancel={() => {}} onSaved={() => {}} />))

    await screen.findByLabelText('Choisir un bloc réutilisable')
    await user.selectOptions(screen.getByLabelText('Choisir un bloc réutilisable'), '3')
    await user.click(screen.getByRole('button', { name: /Supprimer le bloc/i }))
    await waitFor(() => expect(kbApi.removeBloc).toHaveBeenCalledWith(3))
  })
})
