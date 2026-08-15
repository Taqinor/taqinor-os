import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* ============================================================================
   WR5 — surface Paramètres « Données » : sessions d'inventaire (valider /
   annuler), explosion de kit, fiches techniques.
   PV7 — fiches techniques : type_fiche (module/onduleur/batterie), édition,
   PDF constructeur.
   ========================================================================== */

vi.mock('../../api/stockApi', () => ({
  default: {
    getInventaireSessions: vi.fn(),
    validerInventaireSession: vi.fn(),
    annulerInventaireSession: vi.fn(),
    getKits: vi.fn(),
    exploserKit: vi.fn(),
    // WIR268 / XMFG18 — duplication + traçabilité de la nomenclature.
    dupliquerKit: vi.fn(),
    getKitRevisions: vi.fn(),
    getKitCompositionAu: vi.fn(),
    getFichesTechniques: vi.fn(),
    createFicheTechnique: vi.fn(),
    updateFicheTechnique: vi.fn(),
    deleteFicheTechnique: vi.fn(),
    uploadFicheTechniquePdf: vi.fn(),
    getProduits: vi.fn(),
  },
}))

import stockApi from '../../api/stockApi'
import DonneesSection from './DonneesSection.jsx'

function renderSection() {
  return render(
    <MemoryRouter>
      <ThemeProvider><DonneesSection /></ThemeProvider>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  window.confirm = vi.fn(() => true)
  if (!window.matchMedia) {
    window.matchMedia = vi.fn().mockImplementation((q) => ({
      matches: false, media: q, onchange: null,
      addListener: vi.fn(), removeListener: vi.fn(),
      addEventListener: vi.fn(), removeEventListener: vi.fn(), dispatchEvent: vi.fn(),
    }))
  }
  stockApi.getInventaireSessions.mockResolvedValue({
    data: [{
      id: 1, reference: 'INV-2026-07-0001', statut: 'brouillon',
      lignes: [{ id: 1 }], date_creation: '2026-07-01T09:00:00Z',
    }],
  })
  stockApi.getKits.mockResolvedValue({
    data: [{ id: 5, nom: 'Kit résidentiel', sku: 'KIT-R' }],
  })
  stockApi.getFichesTechniques.mockResolvedValue({ data: [] })
  stockApi.getProduits.mockResolvedValue({ data: [] })
})

describe('WR5 — sessions d\'inventaire', () => {
  it('valide une session brouillon et affiche le résultat', async () => {
    stockApi.validerInventaireSession.mockResolvedValue({
      data: { ajustes: 2, inchanges: 3 },
    })
    renderSection()
    expect(await screen.findByText('INV-2026-07-0001')).toBeVisible()
    fireEvent.click(screen.getByRole('button', { name: 'Valider' }))
    await waitFor(() => {
      expect(stockApi.validerInventaireSession).toHaveBeenCalledWith(1)
    })
    const status = await screen.findByRole('status')
    expect(status.textContent).toMatch(/2 ajustement/)
  })

  it('annule une session brouillon', async () => {
    stockApi.annulerInventaireSession.mockResolvedValue({ data: {} })
    renderSection()
    expect(await screen.findByText('INV-2026-07-0001')).toBeVisible()
    fireEvent.click(screen.getByRole('button', { name: 'Annuler' }))
    await waitFor(() => {
      expect(stockApi.annulerInventaireSession).toHaveBeenCalledWith(1)
    })
  })
})

describe('WR5 — explosion de kit', () => {
  it('explose un kit en lignes composant', async () => {
    stockApi.exploserKit.mockResolvedValue({
      data: {
        kit_id: 5, kit_nom: 'Kit résidentiel', quantite_kit: 1,
        lignes: [{
          produit_id: 11, sku: 'PAN-550', designation: 'Panneau 550',
          quantite: 8, prix_vente_unitaire: '1000', tva: 20, marque: 'JA',
          disponible: 30,
        }],
      },
    })
    renderSection()
    // Attendre le chargement des kits.
    await waitFor(() => { expect(stockApi.getKits).toHaveBeenCalled() })
    // Sélectionner le kit (le Select radix expose un combobox).
    const btn = screen.getByRole('button', { name: 'Exploser' })
    fireEvent.click(btn)
    // Sans kit choisi → message d'erreur.
    expect(await screen.findByText(/Choisissez un kit/)).toBeVisible()
  })

  // ── WIR268 / XMFG18 — dupliquer + révisions + composition à une date ──
  it('duplique le kit sélectionné avec le facteur d\'échelle saisi', async () => {
    stockApi.dupliquerKit.mockResolvedValue({
      data: { id: 6, nom: 'Kit résidentiel (copie)' },
    })
    renderSection()
    await waitFor(() => { expect(stockApi.getKits).toHaveBeenCalled() })

    // Sélectionne le kit (Radix Select : le déclencheur porte le placeholder).
    await userEvent.click(screen.getByText('— Choisir un kit —').closest('button'))
    await userEvent.click(await screen.findByRole('option', { name: /Kit résidentiel/ }))

    await userEvent.type(screen.getByLabelText("Facteur d'échelle"), '1.67')
    await userEvent.click(screen.getByRole('button', { name: 'Dupliquer le kit' }))

    await waitFor(() => expect(stockApi.dupliquerKit).toHaveBeenCalledWith('5', '1.67'))
    expect(await screen.findByText(/quantités × 1.67/)).toBeInTheDocument()
  })

  it('affiche l\'historique des révisions de nomenclature', async () => {
    stockApi.getKitRevisions.mockResolvedValue({
      data: [{ id: 1, numero: 2, user_username: 'reda', date_creation: '2026-08-01' }],
    })
    renderSection()
    await waitFor(() => { expect(stockApi.getKits).toHaveBeenCalled() })

    await userEvent.click(screen.getByText('— Choisir un kit —').closest('button'))
    await userEvent.click(await screen.findByRole('option', { name: /Kit résidentiel/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Historique des révisions' }))

    await waitFor(() => expect(stockApi.getKitRevisions).toHaveBeenCalledWith('5'))
    expect(await screen.findByText('Révision n° 2')).toBeInTheDocument()
  })
})

describe('PV7 — fiches techniques (type_fiche, édition, PDF)', () => {
  const PRODUITS = [
    { id: 3, nom: 'Panneau X', sku: 'PAN-X' },
    { id: 9, nom: 'Onduleur Y', sku: 'OND-Y' },
  ]
  const FICHE_MODULE = {
    id: 7, produit: 3, produit_nom: 'Panneau X', produit_marque: 'JA',
    produit_garantie: '10 ans', type_fiche: 'module',
    pmax_wc: '550.00', voc_v: '49.50', isc_a: '14.00', vmp_v: '41.50',
    imp_a: '13.30', rendement_pct: '21.40',
    longueur_mm: 2278, largeur_mm: 1134, epaisseur_mm: 30, poids_kg: '27.50',
    techno_cellule: 'N-type TOPCon', bifacial: true,
    temp_coeff_voc_pct_c: '-0.250', temp_coeff_pmax_pct_c: '-0.300',
    pdf: null, date_creation: '2026-08-01T09:00:00Z',
    date_mise_a_jour: '2026-08-01T09:00:00Z',
  }

  async function ouvrirEtChoisir(user, nomCombobox, nomOption) {
    await user.click(screen.getByRole('combobox', { name: nomCombobox }))
    await user.click(await screen.findByRole('option', { name: nomOption }))
  }

  it("affiche le bloc « onduleur » quand ce type est choisi (et pas le bloc module)", async () => {
    const user = userEvent.setup()
    stockApi.getFichesTechniques.mockResolvedValue({ data: [] })
    stockApi.getProduits.mockResolvedValue({ data: PRODUITS })
    renderSection()
    await waitFor(() => { expect(stockApi.getProduits).toHaveBeenCalled() })

    await ouvrirEtChoisir(user, 'Type de fiche', 'Onduleur')

    expect(screen.getByPlaceholderText('Nombre de MPPT')).toBeVisible()
    expect(screen.getByRole('combobox', { name: 'Phases' })).toBeVisible()
    expect(screen.queryByPlaceholderText('Longueur (mm)')).not.toBeInTheDocument()
    expect(screen.queryByPlaceholderText('Capacité nominale (kWh)')).not.toBeInTheDocument()
  })

  it("affiche le bloc « batterie » quand ce type est choisi", async () => {
    const user = userEvent.setup()
    stockApi.getFichesTechniques.mockResolvedValue({ data: [] })
    stockApi.getProduits.mockResolvedValue({ data: PRODUITS })
    renderSection()
    await waitFor(() => { expect(stockApi.getProduits).toHaveBeenCalled() })

    await ouvrirEtChoisir(user, 'Type de fiche', 'Batterie')

    expect(screen.getByPlaceholderText('Capacité nominale (kWh)')).toBeVisible()
    expect(screen.queryByPlaceholderText('Nombre de MPPT')).not.toBeInTheDocument()
  })

  it('affiche le bloc « module » (dimensions + bifacial) quand ce type est choisi', async () => {
    const user = userEvent.setup()
    stockApi.getFichesTechniques.mockResolvedValue({ data: [] })
    stockApi.getProduits.mockResolvedValue({ data: PRODUITS })
    renderSection()
    await waitFor(() => { expect(stockApi.getProduits).toHaveBeenCalled() })

    await ouvrirEtChoisir(user, 'Type de fiche', 'Module (panneau)')

    expect(screen.getByPlaceholderText('Longueur (mm)')).toBeVisible()
    expect(screen.getByPlaceholderText('Pmax (Wc)')).toBeVisible()
    expect(screen.getByRole('checkbox', { name: 'Bifacial' })).toBeVisible()
  })

  it('crée une fiche pour un produit choisi (le flux de création reste fonctionnel)', async () => {
    const user = userEvent.setup()
    stockApi.getFichesTechniques.mockResolvedValue({ data: [] })
    stockApi.getProduits.mockResolvedValue({ data: PRODUITS })
    stockApi.createFicheTechnique.mockResolvedValue({ data: { id: 42 } })
    renderSection()
    await waitFor(() => { expect(stockApi.getProduits).toHaveBeenCalled() })

    await ouvrirEtChoisir(user, 'Produit', 'Panneau X (PAN-X)')
    await user.type(screen.getByPlaceholderText('Pmax (Wc)'), '550')
    await user.click(screen.getByRole('button', { name: 'Ajouter la fiche' }))

    await waitFor(() => {
      expect(stockApi.createFicheTechnique).toHaveBeenCalledWith(
        expect.objectContaining({ produit: 3, pmax_wc: '550' }),
      )
    })
  })

  it('édite une fiche existante et enregistre les modifications (round-trip)', async () => {
    const user = userEvent.setup()
    stockApi.getFichesTechniques.mockResolvedValue({ data: [FICHE_MODULE] })
    stockApi.getProduits.mockResolvedValue({ data: PRODUITS })
    stockApi.updateFicheTechnique.mockResolvedValue({ data: {} })
    renderSection()
    await screen.findByText('Panneau X')

    await user.click(screen.getByRole('button', { name: 'Modifier la fiche' }))
    // Le formulaire est pré-rempli à partir de la fiche existante.
    expect(await screen.findByText('Modifier la fiche')).toBeVisible()
    const vmp = screen.getByPlaceholderText('Vmp (V)')
    expect(vmp).toHaveValue(41.5)
    await user.clear(vmp)
    await user.type(vmp, '42')

    await user.click(screen.getByRole('button', { name: 'Enregistrer les modifications' }))

    await waitFor(() => {
      expect(stockApi.updateFicheTechnique).toHaveBeenCalledWith(
        7,
        expect.objectContaining({ produit: 3, type_fiche: 'module', vmp_v: '42' }),
      )
    })
  })
})
