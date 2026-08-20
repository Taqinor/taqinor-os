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
  },
}))

import stockApi from '../../api/stockApi'
import { ProduitDetail } from './ProduitDetail.jsx'
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

/* ============================================================================
   PVFCH (fondateur 20/08/2026) — la fiche STRUCTURÉE est VISIBLE et MODIFIABLE
   depuis le visualiseur. « i am expecting a fiche produit that includes all the
   data separately, that I can change — number of MPPT, range of each MPPT,
   battery voltage… » : ces champs existaient (FicheTechnique) et étaient
   éditables dans ProduitForm, mais cet onglet n'affichait que de la prose.
   ========================================================================== */

describe('PVFCH — fiche technique structurée dans le visualiseur', () => {
  const onduleur = { ...produit, id: 9, nom: 'Onduleur hybride Deye 10kW', sku: 'OND-H-10' }

  const ficheOnduleur = (over = {}) => ({
    id: 3, produit: 9, type_fiche: 'onduleur',
    ond_ac_kw: '10.00', ond_phases: 3, ond_n_mppt: 2,
    ond_mppt_v_min: '200.0', ond_mppt_v_max: '650.0',
    ond_v_max_abs: '800.0', ond_i_max_mppt_a: '26.0',
    ond_rendement_euro_pct: '97.0',
    ond_v_demarrage_v: '160.0', ond_isc_max_mppt_a: '39.0',
    ond_bat_aucune: false, ond_bat_v_min: '40.0', ond_bat_v_max: '60.0',
    ...over,
  })

  const ouvrirOnglet = async (props = {}) => {
    render(<ProduitDetail produit={onduleur} onClose={() => {}} {...props} />, { wrapper })
    await userEvent.click(screen.getByRole('tab', { name: 'Fiche technique' }))
    return screen.findByTestId('pdet-fiche-structuree')
  }

  it('affiche chaque variable SÉPARÉMENT, avec son libellé français', async () => {
    stockApi.getFichesTechniques.mockResolvedValue({ data: [ficheOnduleur()] })
    stockApi.produitPrevisionnel.mockResolvedValue({ data: null })
    const bloc = await ouvrirOnglet()

    expect(bloc).toHaveTextContent("Nombre d'entrées MPPT")
    expect(screen.getByTestId('pdet-ft-ond_n_mppt')).toHaveTextContent('2')
    // La plage MPPT : deux bornes, deux lignes — jamais un intervalle opaque.
    expect(screen.getByTestId('pdet-ft-ond_mppt_v_min')).toHaveTextContent('200.0')
    expect(screen.getByTestId('pdet-ft-ond_mppt_v_max')).toHaveTextContent('650.0')
    // La tension batterie, l'autre variable nommée par le fondateur.
    expect(screen.getByTestId('pdet-ft-ond_bat_v_min')).toHaveTextContent('40.0')
    expect(screen.getByTestId('pdet-ft-ond_bat_v_max')).toHaveTextContent('60.0')
    // La borne BLOQUANTE du dimensionnement, et les phases en toutes lettres.
    expect(screen.getByTestId('pdet-ft-ond_v_max_abs')).toHaveTextContent('800.0')
    expect(screen.getByTestId('pdet-ft-ond_phases')).toHaveTextContent('Triphasé')
  })

  it('un champ vide dit « à renseigner » — jamais un défaut ni un zéro', async () => {
    stockApi.getFichesTechniques.mockResolvedValue({
      data: [ficheOnduleur({ ond_v_max_abs: null, ond_n_mppt: null })],
    })
    stockApi.produitPrevisionnel.mockResolvedValue({ data: null })
    await ouvrirOnglet()

    expect(screen.getByTestId('pdet-ft-ond_v_max_abs')).toHaveTextContent('à renseigner')
    expect(screen.getByTestId('pdet-ft-ond_n_mppt')).toHaveTextContent('à renseigner')
    // Le trou doit se VOIR comme un trou : surtout pas « 600 » ni « 2 ».
    expect(screen.getByTestId('pdet-ft-ond_v_max_abs')).not.toHaveTextContent('600')
    expect(screen.getByTestId('pdet-ft-ond_n_mppt')).not.toHaveTextContent('2')
  })

  it('« aucune batterie » se DIT plutôt que de laisser deux lignes vides', async () => {
    stockApi.getFichesTechniques.mockResolvedValue({
      data: [ficheOnduleur({ ond_bat_aucune: true, ond_bat_v_min: null, ond_bat_v_max: null })],
    })
    stockApi.produitPrevisionnel.mockResolvedValue({ data: null })
    await ouvrirOnglet()
    expect(screen.getByTestId('pdet-ft-ond_bat_v_min'))
      .toHaveTextContent('Aucune batterie compatible')
  })

  it('« Modifier la fiche » ouvre l\'édition du MÊME produit', async () => {
    stockApi.getFichesTechniques.mockResolvedValue({ data: [ficheOnduleur()] })
    stockApi.produitPrevisionnel.mockResolvedValue({ data: null })
    const onEdit = vi.fn()
    await ouvrirOnglet({ onEdit })

    await userEvent.click(screen.getByTestId('pdet-modifier-fiche'))
    expect(onEdit).toHaveBeenCalledTimes(1)
    expect(onEdit.mock.calls[0][0]).toMatchObject({ id: 9 })
  })

  it('sans droit d\'écriture (pas de `onEdit`), aucun bouton de modification', async () => {
    stockApi.getFichesTechniques.mockResolvedValue({ data: [ficheOnduleur()] })
    stockApi.produitPrevisionnel.mockResolvedValue({ data: null })
    await ouvrirOnglet()
    expect(screen.queryByTestId('pdet-modifier-fiche')).not.toBeInTheDocument()
  })

  it('un produit SANS fiche ne rend aucun bloc structuré vide', async () => {
    stockApi.getFichesTechniques.mockResolvedValue({ data: [] })
    stockApi.produitPrevisionnel.mockResolvedValue({ data: null })
    render(<ProduitDetail produit={onduleur} onClose={() => {}} />, { wrapper })
    await userEvent.click(screen.getByRole('tab', { name: 'Fiche technique' }))
    await screen.findByTestId('pdet-fiche-technique')
    expect(screen.queryByTestId('pdet-fiche-structuree')).not.toBeInTheDocument()
  })
})
