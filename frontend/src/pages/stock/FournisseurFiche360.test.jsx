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
    // WIR219 — fiche fournisseur (candidature portail) + décision admin.
    getFournisseur: vi.fn(),
    deciderCandidatureFournisseur: vi.fn(),
    // NTP2P8 — badge de score de risque en tête de fiche.
    getScoreRisqueFournisseur: vi.fn(),
    performanceFournisseur: vi.fn(),
    getBonsCommandeFournisseurDe: vi.fn(),
    getFacturesFournisseurDe: vi.fn(),
    getRetoursFournisseurDe: vi.fn(),
    getDocumentsConformiteFournisseur: vi.fn(),
    // WIR108 — acomptes/avoirs/contacts.
    getAcomptesFournisseurDe: vi.fn(),
    createAcompteFournisseur: vi.fn(),
    getAvoirsFournisseurDe: vi.fn(),
    createAvoirFournisseur: vi.fn(),
    validerAvoirFournisseur: vi.fn(),
    imputerAvoirFournisseur: vi.fn(),
    getContactsFournisseurDe: vi.fn(),
    createContactFournisseur: vi.fn(),
    updateContactFournisseur: vi.fn(),
    deleteContactFournisseur: vi.fn(),
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
  // NTP2P8 — défaut neutre : le badge de score ne doit jamais faire échouer
  // un test qui ne le concerne pas (chaque test peut le surcharger).
  stockApi.getScoreRisqueFournisseur.mockResolvedValue({ data: null })
  // WIR219 — défaut neutre : fournisseur historique (candidature déjà validée),
  // aucun bandeau — les tests qui la concernent surchargent ce mock.
  stockApi.getFournisseur.mockResolvedValue({
    data: { id: 7, nom: 'JA Solar', statut_validation: 'valide' },
  })
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
        // PACT23 — `solde_total_du` est un `str(Decimal)` côté serveur
        // (views/fournisseur.py:395, `str(solde_total_du)`), jamais un
        // nombre JS : le mock doit refléter le texte décimal réel, formatMAD
        // (lib/format.toNumber) le parse déjà correctement des deux côtés.
        solde_total_du: '1234.50', factures_ouvertes: 4, score_performance: 87,
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
      data: {
        nb_bons: 5, avg_lead_time_days: 4, fill_rate_pct: 92, nb_retours: 1, return_rate_pct: 2,
        // PACT23 — `total_achats_ht` est un `str(Decimal)` côté serveur
        // (services.py:2910, `str(total_achats)`), jamais un nombre JS.
        total_achats_ht: '5000.00',
      },
    })
    stockApi.getBonsCommandeFournisseurDe.mockResolvedValue({ data: [] })
    stockApi.getFacturesFournisseurDe.mockResolvedValue({ data: [] })
    stockApi.getRetoursFournisseurDe.mockResolvedValue({ data: [] })
    stockApi.getDocumentsConformiteFournisseur.mockResolvedValue({ data: [] })

    renderPage()

    const panel = await screen.findByTestId('f360-tab-performance')
    expect(within(panel).getByText('5')).toBeInTheDocument()
    expect(within(panel).getByText('4 j')).toBeInTheDocument()
    // PACT23 — le texte décimal du serveur est bien formaté en MAD, jamais
    // comparé numériquement à la chaîne brute.
    expect(within(panel).getByText('5 000,00 MAD')).toBeInTheDocument()
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

describe('WIR108 — acomptes, avoirs, contacts', () => {
  const stubCommon = () => {
    stockApi.getFournisseur360.mockImplementation(rejectNotFound)
    stockApi.performanceFournisseur.mockImplementation(rejectNotFound)
    stockApi.getFacturesFournisseurDe.mockResolvedValue({ data: [] })
    stockApi.getRetoursFournisseurDe.mockResolvedValue({ data: [] })
    stockApi.getDocumentsConformiteFournisseur.mockResolvedValue({ data: [] })
  }

  it('Acomptes : liste les acomptes et permet d\'en créer un rattaché à un BCF', async () => {
    stubCommon()
    stockApi.getBonsCommandeFournisseurDe.mockResolvedValue({
      data: [{ id: 11, reference: 'BCF-11' }],
    })
    stockApi.getAcomptesFournisseurDe.mockResolvedValue([
      { id: 1, bon_commande: 11, bon_commande_reference: 'BCF-11', montant: 5000, montant_consomme: 0 },
    ])
    stockApi.createAcompteFournisseur.mockResolvedValue({ data: {} })

    renderPage({ authState: { role: 'admin' } })

    await userEvent.click(await screen.findByRole('tab', { name: /Acomptes/ }))
    const panel = await screen.findByTestId('f360-tab-acomptes')
    expect(within(panel).getByText(/BCF-11/)).toBeInTheDocument()

    await userEvent.click(within(panel).getByRole('button', { name: /Nouvel acompte/ }))
    const montant = await screen.findByLabelText(/Montant \(MAD\)/)
    await userEvent.type(montant, '2000')
    await userEvent.click(screen.getByRole('button', { name: 'Enregistrer' }))

    await waitFor(() => {
      expect(stockApi.createAcompteFournisseur).toHaveBeenCalledWith(
        expect.objectContaining({ bon_commande: 11, montant: 2000 }))
    })
  })

  it('Avoirs : créer un avoir puis l\'imputer réduit le solde dû', async () => {
    stubCommon()
    stockApi.getBonsCommandeFournisseurDe.mockResolvedValue({ data: [] })
    stockApi.getFacturesFournisseurDe.mockResolvedValue({
      data: [{ id: 21, reference: 'FAF-21', solde_du: 1000 }],
    })
    stockApi.getAvoirsFournisseurDe.mockResolvedValue({
      data: [{ id: 5, reference: 'AVF-000001', statut: 'valide', montant_ttc: 300, montant_disponible: 300 }],
    })
    stockApi.imputerAvoirFournisseur.mockResolvedValue({ data: {} })

    renderPage({ authState: { role: 'admin' }, fournisseurId: '9' })

    await userEvent.click(await screen.findByRole('tab', { name: /Avoirs/ }))
    const panel = await screen.findByTestId('f360-tab-avoirs')
    expect(within(panel).getByText('AVF-000001')).toBeInTheDocument()

    await userEvent.click(within(panel).getByRole('button', { name: 'Imputer' }))
    const dialog = await screen.findByRole('dialog')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Imputer' }))

    await waitFor(() => {
      expect(stockApi.imputerAvoirFournisseur).toHaveBeenCalledWith(
        5, expect.objectContaining({ facture: 21 }))
    })
  })

  it('Contacts : ajoute un contact secondaire', async () => {
    stubCommon()
    stockApi.getBonsCommandeFournisseurDe.mockResolvedValue({ data: [] })
    stockApi.getContactsFournisseurDe.mockResolvedValue({ data: [] })
    stockApi.createContactFournisseur.mockResolvedValue({ data: {} })

    renderPage({ authState: { role: 'admin' } })

    await userEvent.click(await screen.findByRole('tab', { name: /Contacts/ }))
    const panel = await screen.findByTestId('f360-tab-contacts')
    expect(within(panel).getByText('Aucun contact secondaire.')).toBeInTheDocument()

    await userEvent.click(within(panel).getByRole('button', { name: /Nouveau contact/ }))
    // Champ `required` : le libellé accessible porte l'astérisque
    // (« Nom* ») — préfixe plutôt que chaîne exacte.
    await userEvent.type(await screen.findByLabelText(/^Nom/), 'Jean Dupont')
    await userEvent.click(screen.getByRole('button', { name: 'Enregistrer' }))

    await waitFor(() => {
      expect(stockApi.createContactFournisseur).toHaveBeenCalledWith(
        expect.objectContaining({ nom: 'Jean Dupont' }))
    })
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

// ── NTPRT25 / WIR219 — candidature portail en attente ───────────────────────
describe('WIR219 — candidature d\'auto-inscription au portail', () => {
  const enAttente = {
    data: { id: 7, nom: 'Nouveau Candidat SARL', statut_validation: 'en_attente_validation' },
  }

  it('un admin peut valider la candidature depuis la fiche', async () => {
    stockApi.getFournisseur360.mockImplementation(rejectNotFound)
    stockApi.getFournisseur.mockResolvedValue(enAttente)
    stockApi.deciderCandidatureFournisseur.mockResolvedValue({
      data: { id: 7, statut_validation: 'valide' },
    })
    renderPage()

    await userEvent.click(await screen.findByRole('button', { name: 'Valider la candidature' }))
    await waitFor(() => expect(stockApi.deciderCandidatureFournisseur)
      .toHaveBeenCalledWith('7', true))
    // Validée : le bandeau bloquant disparaît.
    await waitFor(() => expect(
      screen.queryByRole('button', { name: 'Valider la candidature' })).toBeNull())
  })

  it('un responsable non-admin voit le blocage mais AUCUNE action de décision', async () => {
    stockApi.getFournisseur360.mockImplementation(rejectNotFound)
    stockApi.getFournisseur.mockResolvedValue(enAttente)
    renderPage({ authState: { role: 'responsable', permissions: [] } })

    expect(await screen.findByText(/Candidature en attente de validation/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Valider la candidature' })).toBeNull()
  })

  it('affiche le 403 serveur en français si la décision est refusée', async () => {
    stockApi.getFournisseur360.mockImplementation(rejectNotFound)
    stockApi.getFournisseur.mockResolvedValue(enAttente)
    stockApi.deciderCandidatureFournisseur.mockRejectedValue({ response: { status: 403 } })
    renderPage()

    await userEvent.click(await screen.findByRole('button', { name: 'Valider la candidature' }))
    expect(await screen.findByText(/Réservé à l'administrateur/)).toBeInTheDocument()
  })
})
