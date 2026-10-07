import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import authReducer from '../../features/auth/store/authSlice'

/* ============================================================================
   ASTK15 (C-ASTK-002, D-ASTK-2) — un compte SANS `prix_achat_voir` reçoit des
   réponses dont le serveur a RETIRÉ les prix et montants d'achat (ASTK10-13 :
   lignes de BCF sans prix_achat_unitaire/total_achat, BCF sans total_achat,
   factures sans montants ni solde). Les écrans achats doivent alors :
     - n'afficher ni « NaN », ni « 0,00 », ni « undefined » — « — » à la place ;
     - masquer « PDF (interne) », « Historique des prix », les files
       « Comptes à payer » / « En exception », les onglets « Accords de prix »
       et « Tarif » (import/export des prix) — jamais de requête 403 ;
     - n'envoyer AUCUN `prix_achat_unitaire` à l'enregistrement d'un BCF
       (jamais un 0 qui écraserait le prix réel).
   Composants réels ; seule l'API est simulée (frontière réseau).
   ========================================================================== */

vi.mock('../../api/stockApi', () => ({
  default: {
    // BCF
    bcfPdf: vi.fn(),
    createBonCommandeFournisseur: vi.fn(),
    updateBonCommandeFournisseur: vi.fn(() => Promise.resolve({ data: {} })),
    prixEffectifFournisseur: vi.fn(() => Promise.resolve({ data: {} })),
    getBcfSimilaires: vi.fn(() => Promise.resolve({ data: [] })),
    getHistoriquePrixBcf: vi.fn(),
    getCategories: vi.fn(() => Promise.resolve({ data: { results: [] } })),
    // Factures
    getFacturesFournisseur: vi.fn(),
    getComptesAPayer: vi.fn(),
    getFacturesEnException: vi.fn(),
    getFactureFournisseur: vi.fn(),
    getFournisseurs: vi.fn(() => Promise.resolve({ data: [] })),
    getBonsCommandeFournisseur: vi.fn(() => Promise.resolve({ data: [] })),
    acomptesFournisseurOuverts: vi.fn(() => Promise.resolve({ data: [] })),
    // Fiche 360
    getFournisseur360: vi.fn(),
    getScoreRisqueFournisseur: vi.fn(() => Promise.resolve({ data: null })),
    performanceFournisseur: vi.fn(),
    getBonsCommandeFournisseurDe: vi.fn(() => Promise.resolve({ data: [] })),
    getFacturesFournisseurDe: vi.fn(),
    getRetoursFournisseurDe: vi.fn(() => Promise.resolve({ data: [] })),
    getDocumentsConformiteFournisseur: vi.fn(() => Promise.resolve({ data: [] })),
    getAcomptesFournisseurDe: vi.fn(() => Promise.resolve({ data: [] })),
    getAvoirsFournisseurDe: vi.fn(() => Promise.resolve({ data: [] })),
    getContactsFournisseurDe: vi.fn(() => Promise.resolve({ data: [] })),
    getFournisseur: vi.fn(() => Promise.resolve({ data: { id: 7, statut_validation: 'valide' } })),
    exportPrixFournisseurXlsx: vi.fn(),
    importPrixFournisseurXlsx: vi.fn(),
  },
}))

vi.mock('../../api/coreApi', () => ({
  default: { utilisateurs: { list: vi.fn().mockResolvedValue({ data: [] }) } },
}))

import stockApi from '../../api/stockApi'
import { BcfDetail } from './BonsCommandeFournisseur.jsx'
import FacturesFournisseur from './FacturesFournisseur.jsx'
import FournisseurFiche360 from './FournisseurFiche360.jsx'

const COMMERCIAL = { role: 'normal', role_nom: 'Commercial', permissions: ['stock_voir'] }
// Un acheteur qui commande (ASTK21 : `achats_commander`) sans voir les prix.
const ACHETEUR_SANS_PRIX = {
  role: 'normal', role_nom: 'Acheteur', permissions: ['stock_voir', 'achats_commander'],
}
const DIRECTEUR = {
  role: 'admin', role_nom: 'Directeur',
  permissions: ['stock_voir', 'stock_modifier', 'prix_achat_voir', 'achats_commander'],
}

function makeStore(auth) {
  return configureStore({
    reducer: { auth: authReducer },
    preloadedState: {
      auth: { user: { id: 1 }, ...auth, isAuthenticated: true, loading: false },
    },
  })
}

function renderAvec(auth, ui, route = '/') {
  return render(
    <Provider store={makeStore(auth)}>
      <MemoryRouter initialEntries={[route]}>
        <ThemeProvider>{ui}</ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

// Forme RÉELLE d'un BCF servi sans `prix_achat_voir` (ASTK10) : ni
// `total_achat` ni `acomptes` sur le bon, ni prix/total sur ses lignes.
const BCF_MASQUE = {
  id: 42, reference: 'BCF-2026-10-0042', statut: 'brouillon', fournisseur: 3,
  fournisseur_nom: 'JA Solar', date_commande: '2026-10-01', note: '',
  lignes: [{
    id: 9, produit: 5, produit_nom: 'Onduleur 5 kW', produit_sku: 'OND-5',
    designation: '', quantite: 4, quantite_recue: 0,
  }],
}

function sansNaN() {
  const texte = document.body.textContent
  expect(texte).not.toMatch(/NaN/)
  expect(texte).not.toMatch(/undefined/)
  expect(texte).not.toMatch(/0,00/)
}

beforeEach(() => {
  vi.clearAllMocks()
  if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {}
})

describe('ASTK15 — BCF sans prix d\'achat visibles', () => {
  it('affiche « — » partout et masque PDF interne + historique des prix', async () => {
    renderAvec(COMMERCIAL, (
      <BcfDetail bcf={BCF_MASQUE} fournisseurs={[{ id: 3, nom: 'JA Solar' }]}
                 produits={[{ id: 5, nom: 'Onduleur 5 kW', sku: 'OND-5' }]}
                 onClose={() => {}} onSaved={() => {}} />
    ))
    expect(await screen.findByText(/Total achat HT \(interne\)/)).toHaveTextContent('—')
    sansNaN()
    expect(screen.queryByRole('button', { name: /PDF \(interne\)/ })).toBeNull()
    expect(screen.queryByRole('button', { name: /Historique des prix/ })).toBeNull()
    expect(stockApi.prixEffectifFournisseur).not.toHaveBeenCalled()
  })

  it("n'envoie pas de prix : aucun prix_achat_unitaire dans le payload d'enregistrement", async () => {
    renderAvec(ACHETEUR_SANS_PRIX, (
      <BcfDetail bcf={BCF_MASQUE} fournisseurs={[{ id: 3, nom: 'JA Solar' }]}
                 produits={[{ id: 5, nom: 'Onduleur 5 kW', sku: 'OND-5' }]}
                 onClose={() => {}} onSaved={() => {}} />
    ))
    fireEvent.click(await screen.findByRole('button', { name: /^Enregistrer/ }))
    await waitFor(() => expect(stockApi.updateBonCommandeFournisseur).toHaveBeenCalled())
    const [id, payload] = stockApi.updateBonCommandeFournisseur.mock.calls[0]
    expect(id).toBe(42)
    expect(payload.lignes).toHaveLength(1)
    expect(payload.lignes[0]).not.toHaveProperty('prix_achat_unitaire')
    expect(payload.lignes[0].quantite).toBe(4)
  })

  it('le Directeur (prix_achat_voir) garde prix, total et PDF interne', async () => {
    const bcf = {
      ...BCF_MASQUE, total_achat: '4000.00',
      lignes: [{ ...BCF_MASQUE.lignes[0], prix_achat_unitaire: '1000.00', total_achat: '4000.00' }],
    }
    renderAvec(DIRECTEUR, (
      <BcfDetail bcf={bcf} fournisseurs={[{ id: 3, nom: 'JA Solar' }]}
                 produits={[{ id: 5, nom: 'Onduleur 5 kW', sku: 'OND-5' }]}
                 onClose={() => {}} onSaved={() => {}} />
    ))
    expect(await screen.findByRole('button', { name: /PDF \(interne\)/ })).toBeInTheDocument()
    expect(screen.getByText(/Total achat HT \(interne\)/).textContent).toMatch(/4\s?000,00/)
    fireEvent.click(screen.getByRole('button', { name: /^Enregistrer/ }))
    await waitFor(() => expect(stockApi.updateBonCommandeFournisseur).toHaveBeenCalled())
    expect(stockApi.updateBonCommandeFournisseur.mock.calls[0][1].lignes[0].prix_achat_unitaire).toBe(1000)
  })
})

describe('ASTK15 — factures fournisseur sans montants', () => {
  it('liste et détail sans NaN, sans files de montants ni PDF interne', async () => {
    // Forme RÉELLE (ASTK11) : ni montants ni solde sur la facture.
    const facture = {
      id: 1, reference: 'FF-2026-10-0001', fournisseur_nom: 'JA Solar',
      ref_fournisseur: 'F-77', statut: 'a_payer', statut_controle: 'normale',
      date_echeance: '2026-11-01', paiements: [],
    }
    stockApi.getFacturesFournisseur.mockResolvedValue({ data: [facture] })
    stockApi.getFactureFournisseur.mockResolvedValue({ data: facture })
    renderAvec(COMMERCIAL, <FacturesFournisseur />)
    expect((await screen.findAllByText('FF-2026-10-0001'))[0]).toBeInTheDocument()
    sansNaN()
    expect(screen.queryByRole('button', { name: /Comptes à payer/ })).toBeNull()
    expect(screen.queryByRole('button', { name: /En exception/ })).toBeNull()
    expect(stockApi.getComptesAPayer).not.toHaveBeenCalled()
    await userEvent.click(screen.getAllByText('FF-2026-10-0001')[0])
    await waitFor(() => expect(stockApi.getFactureFournisseur).toHaveBeenCalled())
    await screen.findByText('Déjà payé')
    sansNaN()
    expect(screen.queryByRole('button', { name: /PDF \(interne\)/ })).toBeNull()
  })
})

describe('ASTK15 — fiche fournisseur 360 sans prix d\'achat visibles', () => {
  it('pas d\'onglets Accords de prix / Tarif, soldes en « — », aucune requête de prix', async () => {
    stockApi.getFournisseur360.mockResolvedValue({
      data: { bcf_ouverts: 1, bcf_en_retard: 0, receptions_attendues: 1, factures_ouvertes: 1,
              nb_retours_avoirs: 0, accords_prix_actifs: 1, accords_prix: [{ produit_id: 5 }] },
    })
    // ASTK13 : la performance arrive sans `total_achats_ht`.
    stockApi.performanceFournisseur.mockResolvedValue({
      data: { nb_bons: 1, avg_lead_time_days: null, fill_rate_pct: null, nb_retours: 0, return_rate_pct: null },
    })
    stockApi.getFacturesFournisseurDe.mockResolvedValue({
      data: [{ id: 1, reference: 'FF-1', statut: 'a_payer' }],
    })
    renderAvec(COMMERCIAL, (
      <Routes>
        <Route path="/stock/fournisseurs/:id/360" element={<FournisseurFiche360 />} />
      </Routes>
    ), '/stock/fournisseurs/7/360')
    expect(await screen.findByText('Fiche fournisseur 360')).toBeInTheDocument()
    await waitFor(() => expect(stockApi.performanceFournisseur).toHaveBeenCalled())
    expect(screen.queryByRole('tab', { name: /Accords de prix/ })).toBeNull()
    expect(screen.queryByRole('tab', { name: /Tarif/ })).toBeNull()
    await userEvent.click(screen.getByRole('tab', { name: /Factures/ }))
    expect(await screen.findByText('FF-1')).toBeInTheDocument()
    sansNaN()
    expect(stockApi.exportPrixFournisseurXlsx).not.toHaveBeenCalled()
    expect(stockApi.importPrixFournisseurXlsx).not.toHaveBeenCalled()
  })
})
