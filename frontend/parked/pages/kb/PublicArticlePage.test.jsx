import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import PublicArticlePage from './PublicArticlePage'

vi.mock('../../api/kbApi', () => ({
  default: {
    getPublicArticle: vi.fn(),
  },
}))

import kbApi from '../../api/kbApi'

function renderAt(token) {
  return render(
    <MemoryRouter initialEntries={[`/kb/public/${token}`]}>
      <Routes>
        <Route path="/kb/public/:token" element={<PublicArticlePage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('PublicArticlePage (XKB19)', () => {
  it('affiche le titre et le contenu quand le jeton est valide', async () => {
    kbApi.getPublicArticle.mockResolvedValueOnce({
      data: {
        titre: 'Procédure X',
        corps: 'Contenu de test',
        corps_format: 'texte',
        categorie: 'SAV',
      },
    })
    renderAt('bon-jeton')
    await waitFor(() => expect(screen.getByText('Procédure X')).toBeTruthy())
    expect(screen.getByText('Contenu de test')).toBeTruthy()
    expect(kbApi.getPublicArticle).toHaveBeenCalledWith('bon-jeton')
  })

  it('affiche un message honnête quand le jeton est introuvable (404)', async () => {
    kbApi.getPublicArticle.mockRejectedValueOnce({
      response: { status: 404, data: { detail: "Ce lien est introuvable ou n'est plus disponible." } },
    })
    renderAt('mauvais-jeton')
    await waitFor(() =>
      expect(screen.getByRole('alert')).toHaveTextContent(
        "Ce lien est introuvable ou n'est plus disponible."))
  })

  it('affiche un message d’expiration quand le lien a expiré (410)', async () => {
    kbApi.getPublicArticle.mockRejectedValueOnce({
      response: { status: 410, data: { detail: 'Ce lien a expiré.' } },
    })
    renderAt('jeton-expire')
    await waitFor(() =>
      expect(screen.getByRole('alert')).toHaveTextContent('Ce lien a expiré.'))
  })
})
