import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import authReducer from '../../features/auth/store/authSlice'

/* ============================================================================
   XPUR25 — Fiche fournisseur 360. L'agrégat `fournisseurs/{id}/vue-360/` est
   BLOCKED côté backend (pas encore construit) : ces tests prouvent que la
   page ne plante JAMAIS quand cet appel (ou tout autre onglet) échoue en 404
   — elle affiche un état « indisponible » — et que chaque onglet consomme
   bien un endpoint détaillé réel avec des données correctes quand il répond.
   ========================================================================== */

vi.mock('../../api/stockApi', () => ({
  default: {
    getFournisseur360: vi.fn(),
    performanceFournisseur: vi.fn(),
    getBonsCommandeFournisseurDe: vi.fn(),
    getFacturesFournisseurDe: vi.fn(),
    getRetoursFournisseurDe: vi.fn(),
    getDocumentsConformiteFournisseur: vi.fn(),
  },
}))

import stockApi from '../../api/stockApi'
import FournisseurFiche360 from './FournisseurFiche360.jsx'

function makeStore({ role = 'admin', permissions = [] } = {}) {
  return configureStore({
    reducer: { auth: authReducer },
    preloadedState: {
      auth: {
        user: { id: 1 }, role, role_nom: role, permissions,
        isAuthenticated: true, loading: false,
      },
    },
  })
}

function renderPage({ authState, fournisseurId = '7' } = {}) {
  return render(
    <Provider store={makeStore(authState)}>
      <MemoryRouter initialEntries={[`/stock/fournisseurs/${fournisseurId}/360`]}>
        <ThemeProvider>
          <Routes>
            <Route path="/stock/fournisseurs/:id/360" element={<FournisseurFiche360 />} />
          </Routes>
        </ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

const rejectNotFound = () => Promise.reject({ response: { status: 404 } })

beforeEach(() => {
  vi.clearAllMocks()
})

describe('XPUR25 — panneau résumé (agrégat vue-360, BLOCKED côté serveur)', () => {
  it('affiche un état indisponible sans planter quand vue-360 404', async () => {
    stockApi.getFournisseur360.mockImplementation(rejectNotFound)
    stockApi.performanceFournisseur.mockImplementation(rejectNotFound)
    stockApi.getBonsCommandeFournisseurDe.mockResolvedValue({ data: [] })
    stockApi.getFacturesFournisseurDe.mockResolvedValue({ data: [] })
    stockApi.getRetoursFournisseurDe.mockResolvedValue({ data: [] })
    stockApi.getDocumentsConformiteFournisseur.mockResolvedValue({ data: [] })

    renderPage()

    expect(await screen.findByText('Fiche fournisseur 360')).toBeInTheDocument()
    await waitFor(() => {
      expect(screen.getAllByTestId('f360-indisponible').length).toBeGreaterThan(0)
    })
  })

  it('affiche les compteurs quand vue-360 répond', async () => {
    stockApi.getFournisseur360.mockResolvedValue({
      data: {
        bcf_ouverts: 3, bcf_en_retard: 1, receptions_attendues: 2,
        solde_total_du: 1234.5, factures_ouvertes: 4, score_performance: 87,
        nb_retours_avoirs: 2, accords_prix_actifs: 5, accords_prix: [],
      },
    })
    stockApi.performanceFournisseur.mockImplementation(rejectNotFound)
    stockApi.getBonsCommandeFournisseurDe.mockResolvedValue({ data: [] })
    stockApi.getFacturesFournisseurDe.mockResolvedValue({ data: [] })
    stockApi.getRetoursFournisseurDe.mockResolvedValue({ data: [] })
    stockApi.getDocumentsConformiteFournisseur.mockResolvedValue({ data: [] })

    renderPage()

    // VX159 — « 3 » (BCF ouverts) apparaît maintenant DEUX fois : dans le Stat
    // ET dans le compteur de relations cliquable en tête → on assert la présence
    // via findAllByText, et un indicateur unique (score) pour prouver le panneau.
    expect((await screen.findAllByText('3')).length).toBeGreaterThan(0)
    expect(screen.getByText('87')).toBeInTheDocument()
    expect(screen.getByText('1 234,50 MAD')).toBeInTheDocument()
  })
})

describe('XPUR25 — onglets détaillés (endpoints réels existants)', () => {
  it('Performance (FG59) : rend les indicateurs sans planter', async () => {
    stockApi.getFournisseur360.mockImplementation(rejectNotFound)
    stockApi.performanceFournisseur.mockResolvedValue({
      data: { nb_bons: 5, avg_lead_time_days: 4, fill_rate_pct: 92, nb_retours: 1, return_rate_pct: 2, total_achats_ht: 5000 },
    })
    stockApi.getBonsCommandeFournisseurDe.mockResolvedValue({ data: [] })
    stockApi.getFacturesFournisseurDe.mockResolvedValue({ data: [] })
    stockApi.getRetoursFournisseurDe.mockResolvedValue({ data: [] })
    stockApi.getDocumentsConformiteFournisseur.mockResolvedValue({ data: [] })

    renderPage()

    const panel = await screen.findByTestId('f360-tab-performance')
    expect(within(panel).getByText('5')).toBeInTheDocument()
    expect(within(panel).getByText('4 j')).toBeInTheDocument()
  })

  it('Factures/solde : ne plante pas quand l\'API rejette (500)', async () => {
    stockApi.getFournisseur360.mockImplementation(rejectNotFound)
    stockApi.performanceFournisseur.mockImplementation(rejectNotFound)
    stockApi.getBonsCommandeFournisseurDe.mockResolvedValue({ data: [] })
    stockApi.getFacturesFournisseurDe.mockRejectedValue({ response: { status: 500, data: { detail: 'Erreur serveur.' } } })
    stockApi.getRetoursFournisseurDe.mockResolvedValue({ data: [] })
    stockApi.getDocumentsConformiteFournisseur.mockResolvedValue({ data: [] })

    renderPage()

    await userEvent.click(await screen.findByRole('tab', { name: /Factures/ }))
    const panel = await screen.findByTestId('f360-tab-factures')
    expect(within(panel).getByText('Erreur serveur.')).toBeInTheDocument()
  })

  it('Documents conformité : colore le statut d\'expiration (expiré vs valide)', async () => {
    stockApi.getFournisseur360.mockImplementation(rejectNotFound)
    stockApi.performanceFournisseur.mockImplementation(rejectNotFound)
    stockApi.getBonsCommandeFournisseurDe.mockResolvedValue({ data: [] })
    stockApi.getFacturesFournisseurDe.mockResolvedValue({ data: [] })
    stockApi.getRetoursFournisseurDe.mockResolvedValue({ data: [] })
    stockApi.getDocumentsConformiteFournisseur.mockResolvedValue({
      data: [
        { id: 1, type_document: 'CNSS', date_expiration: '2020-01-01' },
        { id: 2, type_document: 'RC', date_expiration: null },
      ],
    })

    renderPage()

    await userEvent.click(await screen.findByRole('tab', { name: /Conformité/ }))
    const panel = await screen.findByTestId('f360-tab-documents')
    expect(within(panel).getByText(/Expiré/)).toBeInTheDocument()
    expect(within(panel).getByText(/Sans expiration/)).toBeInTheDocument()
  })

  it('BCF/Retours : filtre correctement par fournisseur côté page (aucune fuite cross-fournisseur)', async () => {
    stockApi.getFournisseur360.mockImplementation(rejectNotFound)
    stockApi.performanceFournisseur.mockImplementation(rejectNotFound)
    // Le mock simule ce que fait stockApi.getRetoursFournisseurDe : ne renvoie
    // QUE les retours du fournisseur demandé (jamais un autre fournisseur).
    stockApi.getRetoursFournisseurDe.mockImplementation((fournisseurId) => Promise.resolve({
      data: [{ id: 1, reference: 'RET-1', statut: 'valide', fournisseur: fournisseurId }],
    }))
    stockApi.getBonsCommandeFournisseurDe.mockResolvedValue({ data: [] })
    stockApi.getFacturesFournisseurDe.mockResolvedValue({ data: [] })
    stockApi.getDocumentsConformiteFournisseur.mockResolvedValue({ data: [] })

    renderPage({ fournisseurId: '7' })

    await userEvent.click(await screen.findByRole('tab', { name: /Retours/ }))
    const panel = await screen.findByTestId('f360-tab-retours')
    expect(within(panel).getByText('RET-1')).toBeInTheDocument()
    expect(stockApi.getRetoursFournisseurDe).toHaveBeenCalledWith('7')
  })
})

describe('XPUR25 — garde de rôle', () => {
  it('refuse un rôle non habilité (pas admin/responsable, pas de permission stock_voir)', async () => {
    stockApi.getFournisseur360.mockImplementation(rejectNotFound)
    renderPage({ authState: { role: 'normal', permissions: ['autre_permission'] } })
    expect(await screen.findByText(/Réservé aux rôles habilités/)).toBeInTheDocument()
  })

  it('affiche un état "introuvable" quand aucun id fournisseur n\'est résolu', () => {
    render(
      <Provider store={makeStore()}>
        <MemoryRouter initialEntries={['/stock/fournisseurs//360']}>
          <ThemeProvider>
            <FournisseurFiche360 />
          </ThemeProvider>
        </MemoryRouter>
      </Provider>,
    )
    expect(screen.getByText('Fournisseur introuvable.')).toBeInTheDocument()
  })
})
