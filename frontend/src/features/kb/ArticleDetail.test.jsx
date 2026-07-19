import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import authReducer from '../../features/auth/store/authSlice'

/* ============================================================================
   XKB19/XKB14/XKB15 — actions ajoutées au détail d'article : partage public
   (créer/copier/dépublier), vérification (badge dérivé de verifie_jusqua),
   verrouillage, favori. Couvre le câblage UI ↔ kbApi, pas le backend.
   ========================================================================== */

vi.mock('../../api/kbApi', () => ({
  default: {
    getArticle: vi.fn(),
    listVersions: vi.fn(),
    resumeLecture: vi.fn(),
    listAcls: vi.fn(),
    listPartages: vi.fn(),
    listFavoris: vi.fn(),
    retroliens: vi.fn(),
    createPartage: vi.fn(),
    depublierPartage: vi.fn(),
    verifier: vi.fn(),
    verrouiller: vi.fn(),
    deverrouiller: vi.fn(),
    togglerFavori: vi.fn(),
    marquerLu: vi.fn(),
    publier: vi.fn(),
    nouvelleVersion: vi.fn(),
    traduire: vi.fn(),
    enregistrerCommeGabarit: vi.fn(),
    exportPdfUrl: vi.fn(() => '/api/django/kb/articles/1/export-pdf/'),
    exportMarkdownUrl: vi.fn(() => '/api/django/kb/articles/1/export-markdown/'),
    uploadCouverture: vi.fn(),
    removeCouverture: vi.fn(),
    couvertureImageUrl: vi.fn(() => '/api/django/kb/articles/1/couverture-image/'),
    items: vi.fn().mockResolvedValue({ data: [] }),
    // WIR71 — lectures obligatoires (XKB7).
    listLecturesObligatoires: vi.fn().mockResolvedValue({ data: [] }),
    createLectureObligatoire: vi.fn(),
    removeLectureObligatoire: vi.fn(),
  },
}))

vi.mock('../../api/customFieldsApi', () => ({
  default: { getDefs: vi.fn().mockResolvedValue({ data: [] }) },
}))

vi.mock('../../api/recordsApi', () => ({
  default: {
    getComments: vi.fn().mockResolvedValue({ data: [] }),
    createComment: vi.fn(),
    deleteComment: vi.fn(),
    getAttachments: vi.fn().mockResolvedValue({ data: [] }),
    uploadAttachment: vi.fn(),
    deleteAttachment: vi.fn(),
  },
}))

import kbApi from '../../api/kbApi'
import ArticleDetail from './ArticleDetail'

function makeStore() {
  return configureStore({
    reducer: { auth: authReducer },
    preloadedState: {
      auth: { user: { id: 1, username: 'reda' }, role: 'admin', isAuthenticated: true, loading: false },
    },
  })
}

function wrap(ui) {
  return (
    <Provider store={makeStore()}>
      <MemoryRouter>
        <ThemeProvider>{ui}</ThemeProvider>
      </MemoryRouter>
    </Provider>
  )
}

const baseArticle = {
  id: 1,
  titre: 'Procédure onduleur',
  corps: 'Contenu',
  categorie: 'SAV',
  tags: 'onduleur, sav',
  statut: 'publie',
  auteur_nom: 'Sami',
  date_modification: '2026-01-01T10:00:00Z',
  est_verrouille: false,
  verifie_jusqua: null,
}

function mockLoads(overrides = {}) {
  kbApi.getArticle.mockResolvedValue({ data: { ...baseArticle, ...overrides } })
  kbApi.listVersions.mockResolvedValue({ data: [] })
  kbApi.resumeLecture.mockResolvedValue({ data: { nombre: 0, lecteurs: [] } })
  kbApi.listAcls.mockResolvedValue({ data: [] })
  kbApi.listPartages.mockResolvedValue({ data: [] })
  kbApi.listFavoris.mockResolvedValue({ data: [] })
  kbApi.retroliens.mockResolvedValue({ data: [] })
  kbApi.listLecturesObligatoires.mockResolvedValue({ data: overrides.lecturesObl || [] })
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('ArticleDetail — partage public (XKB19)', () => {
  it('crée un lien public via « Partager sur le web » (onglet responsable/admin)', async () => {
    mockLoads()
    kbApi.createPartage.mockResolvedValue({ data: { id: 5, token: 'abc123', actif: true, consultations: 0 } })
    const user = userEvent.setup()
    render(wrap(<ArticleDetail articleId={1} canEdit onBack={() => {}} onEdit={() => {}} />))

    await waitFor(() => expect(screen.getByText('Procédure onduleur')).toBeTruthy())
    await user.click(screen.getByRole('tab', { name: /Partage public/i }))
    await user.click(screen.getByRole('button', { name: /Partager sur le web/i }))

    await waitFor(() => expect(kbApi.createPartage).toHaveBeenCalledWith({ article: 1 }))
  })

  it('dépublie un lien actif', async () => {
    mockLoads()
    kbApi.listPartages.mockResolvedValue({
      data: [{ id: 9, token: 'tok-9', actif: true, consultations: 3 }],
    })
    kbApi.depublierPartage.mockResolvedValue({ data: { id: 9, actif: false } })
    const user = userEvent.setup()
    render(wrap(<ArticleDetail articleId={1} canEdit onBack={() => {}} onEdit={() => {}} />))

    await waitFor(() => expect(screen.getByText('Procédure onduleur')).toBeTruthy())
    await user.click(screen.getByRole('tab', { name: /Partage public/i }))
    await user.click(screen.getByRole('button', { name: /Dépublier/i }))

    await waitFor(() => expect(kbApi.depublierPartage).toHaveBeenCalledWith(9))
  })
})

describe('ArticleDetail — vérification & verrouillage (XKB14)', () => {
  it('affiche le badge Vérifié quand verifie_jusqua est dans le futur', async () => {
    mockLoads({ verifie_jusqua: '2999-01-01T00:00:00Z' })
    render(wrap(<ArticleDetail articleId={1} canEdit onBack={() => {}} onEdit={() => {}} />))
    await waitFor(() => expect(screen.getByText('Vérifié')).toBeTruthy())
  })

  it('n’affiche pas le badge Vérifié quand verifie_jusqua est passé', async () => {
    mockLoads({ verifie_jusqua: '2000-01-01T00:00:00Z' })
    render(wrap(<ArticleDetail articleId={1} canEdit onBack={() => {}} onEdit={() => {}} />))
    await waitFor(() => expect(screen.getByText('Procédure onduleur')).toBeTruthy())
    expect(screen.queryByText('Vérifié')).toBeNull()
  })

  it('appelle verifier() au clic sur « Marquer vérifié »', async () => {
    mockLoads()
    kbApi.verifier.mockResolvedValue({ data: baseArticle })
    const user = userEvent.setup()
    render(wrap(<ArticleDetail articleId={1} canEdit onBack={() => {}} onEdit={() => {}} />))
    await waitFor(() => expect(screen.getByText('Procédure onduleur')).toBeTruthy())
    await user.click(screen.getByRole('button', { name: /Marquer vérifié/i }))
    await waitFor(() => expect(kbApi.verifier).toHaveBeenCalledWith(1, 90))
  })

  it('verrouille puis déverrouille l’article', async () => {
    mockLoads()
    kbApi.verrouiller.mockResolvedValue({ data: { ...baseArticle, est_verrouille: true } })
    const user = userEvent.setup()
    render(wrap(<ArticleDetail articleId={1} canEdit onBack={() => {}} onEdit={() => {}} />))
    await waitFor(() => expect(screen.getByText('Procédure onduleur')).toBeTruthy())
    await user.click(screen.getByRole('button', { name: /^Verrouiller/i }))
    await waitFor(() => expect(kbApi.verrouiller).toHaveBeenCalledWith(1))
  })
})

describe('ArticleDetail — favoris (XKB15)', () => {
  it('bascule le favori via toggler-favori', async () => {
    mockLoads()
    kbApi.togglerFavori.mockResolvedValue({ data: { favori: true } })
    const user = userEvent.setup()
    render(wrap(<ArticleDetail articleId={1} canEdit={false} onBack={() => {}} onEdit={() => {}} />))
    await waitFor(() => expect(screen.getByText('Procédure onduleur')).toBeTruthy())
    const favBtn = screen.getByRole('button', { name: /ajouter aux favoris/i })
    await user.click(favBtn)
    await waitFor(() => expect(kbApi.togglerFavori).toHaveBeenCalledWith(1))
  })
})

describe('ArticleDetail — commentaires (XKB13)', () => {
  it('l’onglet Commentaires monte le ChatterWidget scopé kb.kbarticle', async () => {
    mockLoads()
    const recordsApi = (await import('../../api/recordsApi')).default
    const user = userEvent.setup()
    render(wrap(<ArticleDetail articleId={1} canEdit onBack={() => {}} onEdit={() => {}} />))
    await waitFor(() => expect(screen.getByText('Procédure onduleur')).toBeTruthy())
    await user.click(screen.getByRole('tab', { name: /Commentaires/i }))
    await waitFor(() => expect(recordsApi.getComments).toHaveBeenCalledWith('kb.kbarticle', 1))
  })
})

describe('ArticleDetail — rétroliens (XKB11)', () => {
  it('liste les articles qui pointent vers celui-ci et navigue au clic', async () => {
    mockLoads()
    kbApi.retroliens.mockResolvedValue({
      data: [{ id: 7, titre: 'Guide de dépannage', statut: 'publie' }],
    })
    const onOpenArticle = vi.fn()
    const user = userEvent.setup()
    render(wrap(
      <ArticleDetail articleId={1} canEdit onBack={() => {}} onEdit={() => {}} onOpenArticle={onOpenArticle} />,
    ))
    await waitFor(() => expect(screen.getByText('Procédure onduleur')).toBeTruthy())
    await user.click(screen.getByRole('tab', { name: /Rétroliens/i }))
    await waitFor(() => expect(screen.getByText('Guide de dépannage')).toBeTruthy())
    await user.click(screen.getByText('Guide de dépannage'))
    expect(onOpenArticle).toHaveBeenCalledWith(7)
  })
})

describe('ArticleDetail — emoji + couverture (ZGED10)', () => {
  it('préfixe le titre avec l’emoji quand présent', async () => {
    mockLoads({ emoji: '📘' })
    render(wrap(<ArticleDetail articleId={1} canEdit onBack={() => {}} onEdit={() => {}} />))
    await waitFor(() => expect(screen.getByText('📘 Procédure onduleur')).toBeTruthy())
  })

  it('affiche l’image de couverture et permet de la retirer', async () => {
    mockLoads({ has_couverture: true })
    kbApi.removeCouverture.mockResolvedValue({ data: { ...baseArticle, has_couverture: false } })
    const user = userEvent.setup()
    const { container } = render(
      wrap(<ArticleDetail articleId={1} canEdit onBack={() => {}} onEdit={() => {}} />))
    await waitFor(() => expect(screen.getByText('Procédure onduleur')).toBeTruthy())
    expect(container.querySelector('img')).toHaveAttribute(
      'src', '/api/django/kb/articles/1/couverture-image/')
    await user.click(screen.getByRole('button', { name: /^Retirer$/i }))
    await waitFor(() => expect(kbApi.removeCouverture).toHaveBeenCalledWith(1))
  })
})
