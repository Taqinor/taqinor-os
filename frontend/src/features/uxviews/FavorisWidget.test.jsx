// NTUX12 — FavorisWidget : autonome (rien si liste vide/en chargement), liste
// les favoris épinglés avec accès direct (clic navigue via ROUTE, même table
// que la palette ⌘K/Récents — aucune route dupliquée).
import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, screen, fireEvent, cleanup, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const navigateMock = vi.fn()
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, useNavigate: () => navigateMock }
})

const listFavorisMock = vi.fn()
vi.mock('../../api/uxviewsApi', () => ({
  default: {
    listFavoris: (...a) => listFavorisMock(...a),
    createFavori: vi.fn(),
    deleteFavori: vi.fn(),
    reordonnerFavori: vi.fn(),
  },
}))

import FavorisWidget from './FavorisWidget'

beforeEach(() => { listFavorisMock.mockReset() })
afterEach(() => { cleanup(); vi.clearAllMocks() })

function renderWidget() {
  return render(<FavorisWidget />, { wrapper: MemoryRouter })
}

describe('FavorisWidget (NTUX12)', () => {
  it('ne rend rien sans favori (autonome)', async () => {
    listFavorisMock.mockResolvedValue({ data: [] })
    const { container } = renderWidget()
    await waitFor(() => expect(listFavorisMock).toHaveBeenCalled())
    expect(container.firstChild).toBeNull()
  })

  it('liste les favoris avec leur libellé résolu serveur', async () => {
    listFavorisMock.mockResolvedValue({
      data: [
        { id: 1, modele: 'installations.installation', object_id: 7, libelle: 'Chantier Nouaceur', ordre: 0 },
        { id: 2, modele: 'crm.lead', object_id: 3, libelle: 'Ali Ben', ordre: 1 },
      ],
    })
    renderWidget()
    expect(await screen.findByTestId('favoris-widget')).toBeInTheDocument()
    expect(screen.getByText('Chantier Nouaceur')).toBeInTheDocument()
    expect(screen.getByText('Ali Ben')).toBeInTheDocument()
  })

  it('cliquer un favori navigue via ROUTE[type](object_id) — accès direct', async () => {
    listFavorisMock.mockResolvedValue({
      data: [{ id: 1, modele: 'crm.lead', object_id: 3, libelle: 'Ali Ben', ordre: 0 }],
    })
    renderWidget()
    fireEvent.click(await screen.findByText('Ali Ben'))
    expect(navigateMock).toHaveBeenCalledWith('/crm/leads?lead=3')
  })

  it('modèle non câblé à ROUTE : reste affiché, jamais masqué ni cassé', async () => {
    listFavorisMock.mockResolvedValue({
      data: [{ id: 1, modele: 'sav.contrat_inconnu', object_id: 9, libelle: 'Contrat X', ordre: 0 }],
    })
    renderWidget()
    expect(await screen.findByText('Contrat X')).toBeInTheDocument()
    fireEvent.click(screen.getByText('Contrat X'))
    expect(navigateMock).not.toHaveBeenCalled()
  })

  it('favori dont la cible a disparu (libelle=null) : libellé de repli, jamais vide', async () => {
    listFavorisMock.mockResolvedValue({
      data: [{ id: 1, modele: 'crm.lead', object_id: 3, libelle: null, ordre: 0 }],
    })
    renderWidget()
    expect(await screen.findByText('Lead')).toBeInTheDocument()
  })

  it('échec de chargement : ne rend rien (jamais un crash visible)', async () => {
    listFavorisMock.mockRejectedValue(new Error('boom'))
    const { container } = renderWidget()
    await waitFor(() => expect(listFavorisMock).toHaveBeenCalled())
    expect(container.firstChild).toBeNull()
  })

  // ── NTUX21 — glisser-déposer (poignée) ──────────────────────────────────
  it('un seul favori : aucune poignée de déplacement (rien à réordonner)', async () => {
    listFavorisMock.mockResolvedValue({
      data: [{ id: 1, modele: 'crm.lead', object_id: 3, libelle: 'Ali Ben', ordre: 0 }],
    })
    renderWidget()
    await screen.findByText('Ali Ben')
    expect(screen.queryByRole('button', { name: /^déplacer /i })).toBeNull()
  })

  it('plusieurs favoris : une poignée de déplacement accessible par favori', async () => {
    listFavorisMock.mockResolvedValue({
      data: [
        { id: 1, modele: 'crm.lead', object_id: 3, libelle: 'Ali Ben', ordre: 0 },
        { id: 2, modele: 'crm.lead', object_id: 4, libelle: 'Sara K', ordre: 1 },
      ],
    })
    renderWidget()
    await screen.findByText('Ali Ben')
    expect(screen.getByRole('button', { name: 'Déplacer Ali Ben' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Déplacer Sara K' })).toBeInTheDocument()
  })
})
