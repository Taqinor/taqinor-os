import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import authReducer from '../../features/auth/store/authSlice'

/* ============================================================================
   ASTK21 (C-ASTK-003, D-ASTK-3) — les gestes achats ont leurs codes serveur
   (`achats_commander`, `achats_receptionner`, `achats_payer`,
   `catalogue_prix_modifier`). L'écran ne montre JAMAIS un bouton que le
   serveur refuserait (403) :
     - Commercial (aucun code achats) : ni « Nouveau bon de commande », ni
       Envoyer / Réviser / Recevoir / Facturer / Payer, ni l'édition en place
       du prix de vente ;
     - Technicien responsable (`achats_receptionner` seul) : Recevoir /
       Confirmer la réception et rien d'autre.
   Composants réels ; auth au store, API simulée (frontière réseau).
   ========================================================================== */

vi.mock('../../api/stockApi', () => ({
  default: {
    getBcfSimilaires: vi.fn(() => Promise.resolve({ data: [] })),
    getCategories: vi.fn(() => Promise.resolve({ data: { results: [] } })),
    getBonsCommandeFournisseur: vi.fn(() => Promise.resolve({ data: [] })),
    getFournisseurs: vi.fn(() => Promise.resolve({ data: [] })),
    getProduits: vi.fn(() => Promise.resolve({ data: [] })),
    getBcfEnRetard: vi.fn(() => Promise.resolve({ data: [] })),
    getSuggestionsConsolidationBcf: vi.fn(() => Promise.resolve({ data: [] })),
    getReceptionsFournisseur: vi.fn(),
    getReceptionFournisseur: vi.fn(),
    getFacturesFournisseur: vi.fn(),
    getFactureFournisseur: vi.fn(),
    acomptesFournisseurOuverts: vi.fn(() => Promise.resolve({ data: [] })),
    getRetoursFournisseur: vi.fn(),
    getRetourFournisseur: vi.fn(),
  },
}))

vi.mock('../../api/coreApi', () => ({
  default: { utilisateurs: { list: vi.fn().mockResolvedValue({ data: [] }) } },
}))

// `useStockFlags` (ReceptionDetail) lit le profil entreprise.
vi.mock('../../api/parametresApi', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    default: { ...actual.default, getProfile: vi.fn(() => Promise.resolve({ data: {} })) },
  }
})

import stockApi from '../../api/stockApi'
import BonsCommandeFournisseur, { BcfDetail } from './BonsCommandeFournisseur.jsx'
import ReceptionsFournisseur from './ReceptionsFournisseur.jsx'
import FacturesFournisseur from './FacturesFournisseur.jsx'
import RetoursFournisseur from './RetoursFournisseur.jsx'
import { CatalogueTable } from './CatalogueTable.jsx'

const COMMERCIAL = {
  role: 'normal', role_nom: 'Commercial',
  permissions: ['stock_voir', 'stock_modifier', 'prix_achat_voir'],
}
const TECHNICIEN = {
  role: 'responsable', role_nom: 'Technicien responsable',
  permissions: ['stock_voir', 'achats_receptionner'],
}
const DIRECTEUR = {
  role: 'admin', role_nom: 'Directeur',
  permissions: ['stock_voir', 'stock_modifier', 'prix_achat_voir', 'achats_commander',
    'achats_receptionner', 'achats_payer', 'catalogue_prix_modifier'],
}

function makeStore(auth) {
  return configureStore({
    reducer: { auth: authReducer },
    preloadedState: { auth: { user: { id: 1 }, ...auth, isAuthenticated: true, loading: false } },
  })
}

function renderAvec(auth, ui) {
  return render(
    <Provider store={makeStore(auth)}>
      <MemoryRouter>
        <ThemeProvider>{ui}</ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

const bcf = (statut) => ({
  id: 42, reference: 'BCF-2026-10-0042', statut, fournisseur: 3, fournisseur_nom: 'JA Solar',
  lignes: [{
    id: 9, produit: 5, produit_nom: 'Onduleur 5 kW', quantite: 4, quantite_recue: 0,
    prix_achat_unitaire: '1000.00', politique_facturation_achat: 'sur_commande',
  }],
})

function detailBcf(auth, statut) {
  return renderAvec(auth, (
    <BcfDetail bcf={bcf(statut)} fournisseurs={[{ id: 3, nom: 'JA Solar' }]}
               produits={[{ id: 5, nom: 'Onduleur 5 kW', politique_facturation_achat: 'sur_commande' }]} onClose={() => {}} onSaved={() => {}} />
  ))
}

const bouton = (nom) => screen.queryByRole('button', { name: nom })

beforeEach(() => {
  vi.clearAllMocks()
  if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {}
  if (!window.matchMedia) {
    window.matchMedia = vi.fn().mockImplementation((q) => ({
      matches: false, media: q, onchange: null,
      addListener: vi.fn(), removeListener: vi.fn(),
      addEventListener: vi.fn(), removeEventListener: vi.fn(), dispatchEvent: vi.fn(),
    }))
  }
})

describe('ASTK21 — bons de commande fournisseur', () => {
  it('commercial : ni Nouveau BCF, ni Enregistrer/Envoyer sur un brouillon', async () => {
    renderAvec(COMMERCIAL, <BonsCommandeFournisseur />)
    await waitFor(() => expect(stockApi.getBonsCommandeFournisseur).toHaveBeenCalled())
    expect(bouton(/Nouveau bon de commande/)).toBeNull()
  })

  it('commercial : brouillon sans Enregistrer / Envoyer au fournisseur / Annuler', async () => {
    detailBcf(COMMERCIAL, 'brouillon')
    expect(await screen.findByText('BCF-2026-10-0042', { exact: false })).toBeInTheDocument()
    expect(bouton(/^Enregistrer$/)).toBeNull()
    expect(bouton(/Envoyer au fournisseur/)).toBeNull()
    expect(bouton(/Annuler le BC/)).toBeNull()
  })

  it('commercial : BCF envoyé sans Recevoir / Réviser / Facturer / WhatsApp', async () => {
    detailBcf(COMMERCIAL, 'envoye')
    expect(await screen.findByText('BCF-2026-10-0042', { exact: false })).toBeInTheDocument()
    expect(bouton(/Recevoir les quantités/)).toBeNull()
    expect(bouton(/Tout recevoir/)).toBeNull()
    expect(bouton(/Réviser/)).toBeNull()
    expect(bouton(/Facturer/)).toBeNull()
    expect(bouton(/Envoyer par WhatsApp/)).toBeNull()
    expect(bouton(/Retour fournisseur/)).toBeNull()
  })

  it('technicien responsable : Recevoir seulement', async () => {
    detailBcf(TECHNICIEN, 'envoye')
    expect(await screen.findByRole('button', { name: /Recevoir les quantités/ })).toBeInTheDocument()
    expect(bouton(/Réviser/)).toBeNull()
    expect(bouton(/Facturer/)).toBeNull()
    expect(bouton(/Annuler le BC/)).toBeNull()
    expect(bouton(/Envoyer par email/)).toBeNull()
  })

  it('directeur : tous les gestes restent proposés', async () => {
    detailBcf(DIRECTEUR, 'envoye')
    expect(await screen.findByRole('button', { name: /Recevoir les quantités/ })).toBeInTheDocument()
    expect(bouton(/Réviser/)).toBeInTheDocument()
    expect(bouton(/Facturer \(sur commande\)/)).toBeInTheDocument()
    expect(bouton(/Annuler le BC/)).toBeInTheDocument()
  })
})

describe('ASTK21 — réceptions, factures, retours', () => {
  const reception = {
    id: 3, reference: 'REC-2026-10-0003', statut: 'brouillon', bon_commande: 42,
    bon_commande_reference: 'BCF-2026-10-0042', fournisseur_nom: 'JA Solar', lignes: [],
  }

  it('commercial : ni Nouvelle réception ni Confirmer', async () => {
    stockApi.getReceptionsFournisseur.mockResolvedValue({ data: [reception] })
    stockApi.getReceptionFournisseur.mockResolvedValue({ data: reception })
    renderAvec(COMMERCIAL, <ReceptionsFournisseur />)
    await userEvent.click((await screen.findAllByText('REC-2026-10-0003'))[0])
    await waitFor(() => expect(stockApi.getReceptionFournisseur).toHaveBeenCalled())
    expect(bouton(/Nouvelle réception/)).toBeNull()
    expect(bouton(/Confirmer/)).toBeNull()
    expect(bouton(/Annuler la réception/)).toBeNull()
  })

  it('technicien responsable : Nouvelle réception + Confirmer la réception', async () => {
    stockApi.getReceptionsFournisseur.mockResolvedValue({ data: [reception] })
    stockApi.getReceptionFournisseur.mockResolvedValue({ data: reception })
    renderAvec(TECHNICIEN, <ReceptionsFournisseur />)
    expect(await screen.findByRole('button', { name: /Nouvelle réception/ })).toBeInTheDocument()
    await userEvent.click((await screen.findAllByText('REC-2026-10-0003'))[0])
    expect(await screen.findByRole('button', { name: /Confirmer/ })).toBeInTheDocument()
  })

  it('commercial sans payer : ni Nouvelle facture ni paiement', async () => {
    const facture = {
      id: 1, reference: 'FF-2026-10-0001', fournisseur_nom: 'JA Solar', statut: 'a_payer',
      statut_controle: 'normale', montant_ttc: '1200.00', total_paye: '0.00', solde_du: '1200.00',
      paiements: [],
    }
    stockApi.getFacturesFournisseur.mockResolvedValue({ data: [facture] })
    stockApi.getFactureFournisseur.mockResolvedValue({ data: facture })
    renderAvec(COMMERCIAL, <FacturesFournisseur />)
    await userEvent.click((await screen.findAllByText('FF-2026-10-0001'))[0])
    await waitFor(() => expect(stockApi.getFactureFournisseur).toHaveBeenCalled())
    await screen.findByText('Déjà payé')
    expect(bouton(/Nouvelle facture/)).toBeNull()
    expect(bouton(/Ajouter le paiement/)).toBeNull()
    expect(bouton(/Régler le solde/)).toBeNull()
  })

  it('commercial sans payer : pas de « Générer l\'avoir » sur un retour validé', async () => {
    const retour = {
      id: 4, reference: 'RTF-2026-10-0004', statut: 'valide', fournisseur_nom: 'JA Solar', lignes: [],
    }
    stockApi.getRetoursFournisseur.mockResolvedValue({ data: [retour] })
    stockApi.getRetourFournisseur.mockResolvedValue({ data: retour })
    renderAvec(COMMERCIAL, <RetoursFournisseur />)
    await userEvent.click((await screen.findAllByText('RTF-2026-10-0004'))[0])
    await waitFor(() => expect(stockApi.getRetourFournisseur).toHaveBeenCalled())
    expect(bouton(/Générer l.avoir/)).toBeNull()
  })
})

describe('ASTK21 — catalogue : prix de vente', () => {
  const produit = {
    id: 1, nom: 'Panneau 550 Wc', sku: 'PAN-550', prix_vente: '1000.00', tva: '20',
    quantite_stock: 12, seuil_alerte: 2, unite: 'piece', is_archived: false,
    categorie: { id: 3, nom: 'Panneaux', ordre: 1 },
  }
  const table = (canEditPrix) => render(
    <MemoryRouter>
      <ThemeProvider>
        <CatalogueTable produits={[produit]} categories={[{ id: 3, nom: 'Panneaux' }]} loading={false}
                        canWrite canEditPrix={canEditPrix} onInlineSave={vi.fn()}
                        onEdit={() => {}} onDelete={() => {}} onHistorique={() => {}} />
      </ThemeProvider>
    </MemoryRouter>,
  )
  const cellulesPrix = () => screen.queryAllByTitle('Double-cliquez pour modifier')
    .filter((b) => /1\s?000[.,]00 HT/.test(b.textContent))

  it('sans catalogue_prix_modifier, le prix de vente n\'est pas éditable en place', () => {
    table(false)
    expect(cellulesPrix()).toHaveLength(0)
  })

  it('avec catalogue_prix_modifier, la cellule prix reste éditable', () => {
    table(true)
    expect(cellulesPrix().length).toBeGreaterThan(0)
  })
})
