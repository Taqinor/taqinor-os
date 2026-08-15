import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* ============================================================================
   ZPUR10 / ZSTK3 — Fiche produit : quantité « en commande » (BCF sources) +
   rapport prévisionnel (disponible + entrées/sorties attendues → solde
   projeté daté). Lecture seule, donnée interne.
   ========================================================================== */

vi.mock('../../api/stockApi', () => ({
  default: {
    produitPrevisionnel: vi.fn(),
    // PV8 — badge de complétude datasheet (onglet « Fiche technique »).
    getFichesTechniques: vi.fn(),
    // XSTK10 / WIR221 — mise au rebut.
    rebuterProduit: vi.fn(),
  },
}))

import stockApi from '../../api/stockApi'
import { ProduitDetail, RebutModal } from './ProduitDetail.jsx'
// APX21 — la lecture de la courbe vit avec les règles de catalogue.
import { pointsCourbePompe } from '../../features/stock/catalogue'

const store = configureStore({
  reducer: { auth: (s = { role: 'Directeur', role_nom: 'Directeur', permissions: [] }) => s },
})
function wrapper({ children }) {
  // VX159 — RelationCounters rend un <Link> : un Router est requis dans le test.
  return <Provider store={store}><MemoryRouter><ThemeProvider>{children}</ThemeProvider></MemoryRouter></Provider>
}

const produit = {
  id: 7,
  nom: 'Panneau 550',
  sku: 'PAN-550',
  quantite_en_commande: 50,
  bcf_sources_en_commande: [
    { bon_commande_id: 12, reference: 'BCF-2026-0012', fournisseur_nom: 'JA Solar', quantite_restante: 50, date_livraison_prevue: '2026-08-01' },
  ],
}

beforeEach(() => {
  vi.clearAllMocks()
  if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {}
  // PV8 — par défaut, aucune fiche technique (les tests qui en ont besoin
  // écrasent ce mock explicitement).
  stockApi.getFichesTechniques.mockResolvedValue({ data: [] })
})

describe('ZPUR10 — onglet « En commande »', () => {
  it('affiche la quantité en commande et ses BCF sources', () => {
    stockApi.produitPrevisionnel.mockResolvedValue({ data: null })
    render(<ProduitDetail produit={produit} onClose={() => {}} />, { wrapper })
    expect(screen.getAllByText('50')[0]).toBeInTheDocument()
    expect(screen.getByText('BCF-2026-0012')).toBeInTheDocument()
    expect(screen.getByText('JA Solar')).toBeInTheDocument()
  })

  it('sans BCF ouvert : message honnête', () => {
    render(<ProduitDetail produit={{ ...produit, quantite_en_commande: 0, bcf_sources_en_commande: [] }} onClose={() => {}} />,
      { wrapper })
    expect(screen.getByText(/Aucun bon de commande ouvert/)).toBeInTheDocument()
  })
})

describe('ZSTK3 — onglet « Prévisionnel »', () => {
  it('affiche le solde projeté et la timeline', async () => {
    stockApi.produitPrevisionnel.mockResolvedValue({
      data: {
        disponible: 10, sorties_attendues: 3, solde_projete: 57,
        timeline: [
          { date: '2026-08-01', type: 'entree', quantite: 50, reference: 'BCF-2026-0012', fournisseur_nom: 'JA Solar', solde_projete: 60 },
          { date: null, type: 'sortie', quantite: -3, reference: null, fournisseur_nom: null, solde_projete: 57 },
        ],
      },
    })
    render(<ProduitDetail produit={produit} onClose={() => {}} />, { wrapper })
    await userEvent.click(screen.getByRole('tab', { name: 'Prévisionnel' }))
    await waitFor(() => expect(stockApi.produitPrevisionnel).toHaveBeenCalledWith(7))
    expect((await screen.findAllByText('57'))[0]).toBeInTheDocument()
    expect(screen.getByText('+50')).toBeInTheDocument()
  })

  it('en cas d\'échec serveur : message indisponible honnête', async () => {
    stockApi.produitPrevisionnel.mockRejectedValue(new Error('boom'))
    render(<ProduitDetail produit={produit} onClose={() => {}} />, { wrapper })
    await userEvent.click(screen.getByRole('tab', { name: 'Prévisionnel' }))
    expect(await screen.findByText(/indisponible/)).toBeInTheDocument()
  })
})

/* ============================================================================
   APX20 — Onglet « Fiche technique ». `marque`, `garantie` (texte) et
   `description` alimentaient déjà les fiches produits des PDF de devis, mais
   aucun écran ne les MONTRAIT ni ne permettait de les saisir.
   ========================================================================== */

describe('APX20 — onglet « Fiche technique »', () => {
  const ficheProduit = (over = {}) => ({
    ...produit,
    marque: 'JA Solar',
    garantie: '12 ans produit, 25 ans performance',
    description: 'Monocristallin demi-cellule, cadre alu anodisé.',
    ...over,
  })

  it('rend marque, garantie et description — celles qui partent sur le devis', async () => {
    render(<ProduitDetail produit={ficheProduit()} onClose={() => {}} />, { wrapper })
    await userEvent.click(screen.getByRole('tab', { name: 'Fiche technique' }))
    expect(await screen.findByText('JA Solar')).toBeInTheDocument()
    expect(screen.getByText('12 ans produit, 25 ans performance')).toBeInTheDocument()
    expect(screen.getByText(/Monocristallin demi-cellule/)).toBeInTheDocument()
  })

  it('un champ vide dit « Non renseigné » au lieu de disparaître', async () => {
    render(
      <ProduitDetail produit={ficheProduit({ marque: null, garantie: '' })} onClose={() => {}} />,
      { wrapper },
    )
    await userEvent.click(screen.getByRole('tab', { name: 'Fiche technique' }))
    // Marque ET garantie manquantes : deux mentions, pas un silence.
    expect((await screen.findAllByText('Non renseigné')).length).toBe(2)
  })

  it('les caractéristiques de pompage n\'apparaissent que sur une pompe', async () => {
    render(<ProduitDetail produit={ficheProduit()} onClose={() => {}} />, { wrapper })
    await userEvent.click(screen.getByRole('tab', { name: 'Fiche technique' }))
    await screen.findByTestId('pdet-fiche-technique')
    expect(screen.queryByText('Puissance pompe (kW)')).toBeNull()
    expect(screen.queryByText('Tension (V)')).toBeNull()
  })

  it('une pompe affiche sa puissance et sa tension', async () => {
    render(
      <ProduitDetail
        produit={ficheProduit({ nom: 'Pompe OSP 30-15', pompe_kw: '4.00', tension_v: 380 })}
        onClose={() => {}}
      />, { wrapper },
    )
    await userEvent.click(screen.getByRole('tab', { name: 'Fiche technique' }))
    expect(await screen.findByText('Puissance pompe (kW)')).toBeInTheDocument()
    expect(screen.getByText('4.00')).toBeInTheDocument()
    expect(screen.getByText('380')).toBeInTheDocument()
  })

  it('n\'expose jamais le prix d\'achat (loi fondateur)', async () => {
    const { container } = render(
      <ProduitDetail produit={ficheProduit({ prix_achat: '742.50' })} onClose={() => {}} />,
      { wrapper },
    )
    await userEvent.click(screen.getByRole('tab', { name: 'Fiche technique' }))
    await screen.findByTestId('pdet-fiche-technique')
    expect(container.textContent).not.toMatch(/742[.,]50/)
  })
})

/* ============================================================================
   PV8 — Badge « complétude datasheet » sur l'onglet « Fiche technique » :
   complet / partiel / absent, calculé depuis la FicheTechnique (PV5) du
   produit (`stockApi.getFichesTechniques(produitId)`, filtrée serveur).
   ========================================================================== */

describe('PV8 — badge de complétude datasheet', () => {
  it("affiche « Fiche absente » quand le produit n'a pas de fiche technique", async () => {
    stockApi.getFichesTechniques.mockResolvedValue({ data: [] })
    render(<ProduitDetail produit={produit} onClose={() => {}} />, { wrapper })
    await userEvent.click(screen.getByRole('tab', { name: 'Fiche technique' }))
    expect(await screen.findByText('Fiche absente')).toBeInTheDocument()
    expect(stockApi.getFichesTechniques).toHaveBeenCalledWith(7)
  })

  it('affiche « Fiche complète » quand tous les champs requis du type sont renseignés', async () => {
    stockApi.getFichesTechniques.mockResolvedValue({
      data: [{
        id: 1, produit: 7, type_fiche: 'module',
        longueur_mm: 2278, largeur_mm: 1134, pmax_wc: '550.00',
        voc_v: '49.50', vmp_v: '41.50', isc_a: '14.00', imp_a: '13.30',
        temp_coeff_pmax_pct_c: '-0.300',
      }],
    })
    render(<ProduitDetail produit={produit} onClose={() => {}} />, { wrapper })
    await userEvent.click(screen.getByRole('tab', { name: 'Fiche technique' }))
    expect(await screen.findByText('Fiche complète')).toBeInTheDocument()
  })

  it('affiche « Fiche partielle » quand des champs requis du type manquent', async () => {
    stockApi.getFichesTechniques.mockResolvedValue({
      data: [{
        id: 1, produit: 7, type_fiche: 'module',
        longueur_mm: 2278, largeur_mm: 1134, pmax_wc: '550.00',
        voc_v: null, vmp_v: '41.50', isc_a: '14.00', imp_a: '13.30',
        temp_coeff_pmax_pct_c: null,
      }],
    })
    render(<ProduitDetail produit={produit} onClose={() => {}} />, { wrapper })
    await userEvent.click(screen.getByRole('tab', { name: 'Fiche technique' }))
    const badge = await screen.findByText('Fiche partielle')
    expect(badge).toBeInTheDocument()
    expect(badge).toHaveAttribute('title', expect.stringContaining('Voc'))
  })
})

/* ============================================================================
   APX21 — La courbe constructeur est enfin TRACÉE. Les 11 pompes OSP 30
   embarquent leur courbe débit→HMT : elle servait uniquement au
   dimensionnement et n'apparaissait qu'en badge TEXTE « courbe constructeur ».
   ========================================================================== */

const COURBE = { debits_m3h: [0, 6, 12, 18], hmt_m: [91, 85, 70, 40] }

describe('APX21 — lecture de la courbe (logique pure)', () => {
  it('appaire débits et hauteurs dans l\'ordre du constructeur', () => {
    expect(pointsCourbePompe(COURBE)).toEqual([
      { debit: 0, hmt: 91 },
      { debit: 6, hmt: 85 },
      { debit: 12, hmt: 70 },
      { debit: 18, hmt: 40 },
    ])
  })

  it('refuse une courbe absente, incomplète ou incohérente', () => {
    expect(pointsCourbePompe(null)).toBeNull()
    expect(pointsCourbePompe({})).toBeNull()
    // Un seul point : rien à tracer.
    expect(pointsCourbePompe({ debits_m3h: [0], hmt_m: [91] })).toBeNull()
    // Longueurs différentes : on ne devine pas un appariement.
    expect(pointsCourbePompe({ debits_m3h: [0, 6], hmt_m: [91] })).toBeNull()
    // Valeurs non numériques : jamais un NaN sur un axe.
    expect(pointsCourbePompe({ debits_m3h: [0, 'x'], hmt_m: [91, 85] })).toBeNull()
  })
})

describe('APX21 — rendu du graphe dans l\'onglet Fiche technique', () => {
  const pompe = (over = {}) => ({
    ...produit,
    nom: 'Pompe OSP 30-15',
    pompe_kw: '4.00',
    tension_v: 380,
    courbe_pompe: COURBE,
    ...over,
  })

  it('une pompe à courbe affiche le graphe, en lecture seule', async () => {
    render(<ProduitDetail produit={pompe()} onClose={() => {}} />, { wrapper })
    await userEvent.click(screen.getByRole('tab', { name: 'Fiche technique' }))
    expect(await screen.findByTestId('pdet-courbe-pompe')).toBeInTheDocument()
    // ChartFrame donne au graphe un nom accessible + un repli tabulaire :
    // la donnée chiffrée reste lisible sans voir les pixels.
    expect(screen.getByRole('img', { name: /Courbe de pompe de Pompe OSP 30-15/ }))
      .toBeInTheDocument()
    // Lecture seule : aucun champ de saisie dans la carte de courbe.
    expect(screen.getByTestId('pdet-courbe-pompe').querySelector('input')).toBeNull()
  })

  it('une pompe SANS courbe ne rend RIEN (jamais de carte vide)', async () => {
    render(
      <ProduitDetail produit={pompe({ courbe_pompe: null })} onClose={() => {}} />,
      { wrapper },
    )
    await userEvent.click(screen.getByRole('tab', { name: 'Fiche technique' }))
    await screen.findByTestId('pdet-fiche-technique')
    expect(screen.queryByTestId('pdet-courbe-pompe')).toBeNull()
    expect(screen.queryByText(/Courbe constructeur/)).toBeNull()
  })

  it('un produit qui n\'est pas une pompe n\'a pas de carte de courbe', async () => {
    render(<ProduitDetail produit={{ ...produit, marque: 'JA Solar' }} onClose={() => {}} />,
      { wrapper })
    await userEvent.click(screen.getByRole('tab', { name: 'Fiche technique' }))
    await screen.findByTestId('pdet-fiche-technique')
    expect(screen.queryByTestId('pdet-courbe-pompe')).toBeNull()
  })
})

// ── XSTK10 / WIR221 — mise au rebut ─────────────────────────────────────────
describe('WIR221 — mise au rebut d\'un produit', () => {
  const storeAdmin = configureStore({
    reducer: { auth: (s = { role: 'admin', role_nom: 'Directeur', permissions: ['stock_modifier'] }) => s },
  })
  function wrapperAdmin({ children }) {
    return (
      <Provider store={storeAdmin}>
        <MemoryRouter><ThemeProvider>{children}</ThemeProvider></MemoryRouter>
      </Provider>
    )
  }

  it('refuse d\'envoyer sans motif (garde serveur reprise côté écran)', async () => {
    render(<RebutModal produit={produit} onClose={() => {}} />, { wrapper: wrapperAdmin })
    await userEvent.type(screen.getByLabelText('Quantité'), '3')
    await userEvent.click(screen.getByRole('button', { name: 'Mettre au rebut' }))
    expect(await screen.findByText('Le motif est obligatoire.')).toBeInTheDocument()
    expect(stockApi.rebuterProduit).not.toHaveBeenCalled()
  })

  it('rebuter 3 unités poste quantité + motif et affiche la valeur perdue', async () => {
    stockApi.rebuterProduit.mockResolvedValue({
      data: { mouvement_id: 88, valeur_perdue: '1350.00' },
    })
    const onDone = vi.fn()
    render(<RebutModal produit={produit} onClose={() => {}} onDone={onDone} />,
      { wrapper: wrapperAdmin })

    await userEvent.type(screen.getByLabelText('Quantité'), '3')
    await userEvent.selectOptions(screen.getByLabelText('Motif (obligatoire)'), 'casse')
    await userEvent.click(screen.getByRole('button', { name: 'Mettre au rebut' }))

    await waitFor(() => expect(stockApi.rebuterProduit).toHaveBeenCalledWith(
      7, { quantite: 3, motif: 'casse' }))
    expect(await screen.findByText(/1350\.00/)).toBeInTheDocument()
    expect(onDone).toHaveBeenCalled()
  })

  it('la fiche produit expose l\'action pour un rôle habilité', () => {
    stockApi.produitPrevisionnel.mockResolvedValue({ data: null })
    render(<ProduitDetail produit={produit} onClose={() => {}} />, { wrapper: wrapperAdmin })
    expect(screen.getByRole('button', { name: 'Mettre au rebut' })).toBeInTheDocument()
  })
})
