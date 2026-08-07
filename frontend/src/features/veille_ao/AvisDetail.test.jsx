import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import authReducer from '../../features/auth/store/authSlice'

/* ============================================================================
   VAO34 — Fiche avis : « Retenir », « Ignorer » (+ règle d'exclusion proposée),
   « Charger le détail » (échec propre), chatter `records` (ChatterWidget).
   Même patron de test que `ArticleDetail.test.jsx` (kb) : Provider Redux +
   MemoryRouter + ThemeProvider, `recordsApi` mocké pour le chatter.
   ========================================================================== */

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  retenir: vi.fn(),
  ignorer: vi.fn(),
  chargerDetail: vi.fn(),
  reglesCreate: vi.fn(),
  navigate: vi.fn(),
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useParams: () => ({ id: '1' }), useNavigate: () => mocks.navigate }
})

vi.mock('../../api/veilleAoApi', () => ({
  default: {
    avis: {
      get: mocks.get, retenir: mocks.retenir, ignorer: mocks.ignorer, chargerDetail: mocks.chargerDetail,
    },
    reglesExclusion: { create: mocks.reglesCreate },
  },
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

import AvisDetail from './AvisDetail'

function makeStore() {
  return configureStore({
    reducer: { auth: authReducer },
    preloadedState: {
      auth: { user: { id: 1, username: 'reda' }, role: 'admin', isAuthenticated: true, loading: false },
    },
  })
}

const renderScreen = () => render(
  <Provider store={makeStore()}>
    <MemoryRouter><ThemeProvider><AvisDetail /></ThemeProvider></MemoryRouter>
  </Provider>,
)

const AVIS = {
  id: 1, objet: 'Fourniture et pose de panneaux solaires', acheteur: 'Commune X',
  lieu: 'Casablanca-Settat', categorie: 'travaux',
  date_limite: '2026-09-15T12:00:00', montant_estime: 850000,
  score: 42, mots_cles_declenches: ['solaire'], statut: 'nouveau',
  url_detail: 'https://marchespublics.gov.ma/detail/123',
  source_libelle: 'Portail officiel',
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.get.mockResolvedValue({ data: AVIS })
})

describe('AvisDetail', () => {
  it('charge la fiche via veilleAoApi.avis.get(id)', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.get).toHaveBeenCalledWith('1'))
    expect(await screen.findByText('Fourniture et pose de panneaux solaires')).toBeInTheDocument()
    expect(screen.getByText('Commune X')).toBeInTheDocument()
  })

  it('monte le chatter records (ChatterWidget) sur le modèle veille_ao.avismarche', async () => {
    const recordsApi = (await import('../../api/recordsApi')).default
    renderScreen()
    await waitFor(() => expect(recordsApi.getComments).toHaveBeenCalledWith('veille_ao.avismarche', 1))
  })

  it('« Retenir » appelle un service RÉEL et navigue vers l’affaire créée', async () => {
    mocks.retenir.mockResolvedValue({ data: { appel_offre_id: 42 } })
    renderScreen()
    await screen.findByText('Fourniture et pose de panneaux solaires')
    fireEvent.click(screen.getByRole('button', { name: 'Retenir' }))
    await waitFor(() => expect(mocks.retenir).toHaveBeenCalledWith('1'))
    await waitFor(() => expect(mocks.navigate).toHaveBeenCalledWith('/ao/affaires/42'))
  })

  it('« Ignorer » demande le motif et propose (opt-in) la règle d’exclusion, jamais créée sans confirmation', async () => {
    mocks.ignorer.mockResolvedValue({ data: {} })
    mocks.reglesCreate.mockResolvedValue({ data: { id: 5 } })
    renderScreen()
    await screen.findByText('Fourniture et pose de panneaux solaires')

    fireEvent.click(screen.getByRole('button', { name: 'Ignorer' }))
    await screen.findByRole('dialog')
    fireEvent.change(screen.getByLabelText('Motif'), { target: { value: 'hors zone' } })

    // Sans cocher la case, confirmer n'appelle QUE ignorer — jamais la règle.
    // Le bouton du dialogue (portail Radix) est le DERNIER « Ignorer » du DOM.
    const boutons = screen.getAllByRole('button', { name: 'Ignorer' })
    fireEvent.click(boutons[boutons.length - 1])
    await waitFor(() => expect(mocks.ignorer).toHaveBeenCalledWith('1', { motif: 'hors zone' }))
    expect(mocks.reglesCreate).not.toHaveBeenCalled()
  })

  it('« Ignorer » + case « créer une règle » cochée : les DEUX services sont appelés, la valeur est pré-remplie', async () => {
    mocks.ignorer.mockResolvedValue({ data: {} })
    mocks.reglesCreate.mockResolvedValue({ data: { id: 5 } })
    renderScreen()
    await screen.findByText('Fourniture et pose de panneaux solaires')

    fireEvent.click(screen.getByRole('button', { name: 'Ignorer' }))
    await screen.findByRole('dialog')
    fireEvent.change(screen.getByLabelText('Motif'), { target: { value: 'hors zone' } })
    fireEvent.click(screen.getByRole('checkbox'))

    const boutons = screen.getAllByRole('button', { name: 'Ignorer' })
    fireEvent.click(boutons[boutons.length - 1])

    await waitFor(() => expect(mocks.ignorer).toHaveBeenCalledWith('1', { motif: 'hors zone' }))
    await waitFor(() => expect(mocks.reglesCreate).toHaveBeenCalledWith(
      expect.objectContaining({ portee: 'acheteur', valeur: 'Commune X', motif: 'hors zone' }),
    ))
  })

  it('« Charger le détail » : un échec laisse l’avis INTACT et affiche un message FR', async () => {
    mocks.chargerDetail.mockRejectedValue({ response: { data: { detail: 'Délai dépassé.' } } })
    renderScreen()
    await screen.findByText('Fourniture et pose de panneaux solaires')
    fireEvent.click(screen.getByRole('button', { name: /Charger le détail/ }))
    expect(await screen.findByText('Délai dépassé.')).toBeInTheDocument()
    // L'avis reste affiché intact — l'objet est toujours là.
    expect(screen.getByText('Fourniture et pose de panneaux solaires')).toBeInTheDocument()
  })

  it('affiche un lien sortant vers l’avis d’origine quand url_detail est connue', async () => {
    renderScreen()
    await screen.findByText('Fourniture et pose de panneaux solaires')
    const lien = screen.getByRole('link', { name: /Voir l’avis d’origine/ })
    expect(lien).toHaveAttribute('href', AVIS.url_detail)
    expect(lien).toHaveAttribute('target', '_blank')
  })
})
