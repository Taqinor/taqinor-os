import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { documentContrat } from '../../test/fixtures/contractSamples'

/* ============================================================================
   ASTK230 (C-ASTK-045, CAT-8) — la fiche produit rend saisissables les champs
   maîtres lus par les consommateurs (rôle de devis, unité, code-barres, code
   SH, pays d'origine, avertissement de vente, paliers, suivi série, politique
   d'achat, classe de danger, cible de réappro, location, abonnement). Contrat
   partagé : produit_champs_maitres.json — LU dans le fichier (PACT10). Les
   listes de choix viennent de la réponse OPTIONS (jamais retapées) ; seuls les
   champs modifiés partent au PATCH (enregistrer sans toucher = rien d'écrasé).
   ========================================================================== */

const contrat = documentContrat('stock', 'produit_champs_maitres')
const enChoix = (paires) => paires.map(([value, display_name]) => ({ value, display_name }))
const OPTIONS_PRODUIT = {
  actions: {
    PUT: {
      role_devis: { choices: contrat.choices.role_devis.valeurs.map((v) => ({ value: v, display_name: v })) },
      classe_danger: { choices: enChoix(contrat.choices.classe_danger.valeurs) },
      periodicite_defaut: { choices: enChoix(contrat.choices.periodicite_defaut.valeurs) },
      politique_facturation_achat: { choices: enChoix(contrat.choices.politique_facturation_achat.valeurs) },
    },
  },
}

const reseau = vi.hoisted(() => ({
  options: vi.fn(),
  get: vi.fn(() => Promise.resolve({ data: [] })),
  post: vi.fn(),
}))
vi.mock('../../api/axios', () => ({ default: reseau }))
vi.mock('../../api/stockApi', async () => ({
  default: (await import('../../test/fixtures/produitFormHarness.jsx')).stockApiSimule(),
}))
vi.mock('../../ui', async (importActual) => {
  const harnais = await import('../../test/fixtures/produitFormHarness.jsx')
  return harnais.uiAvecSelectNatif(await importActual())
})

import ProduitForm from './ProduitForm.jsx'
import { wrapperProduitForm, espionsStock } from '../../test/fixtures/produitFormHarness.jsx'

const BATTERIE = {
  ...contrat.exemple,
  ...contrat.exemple_nouveau_astk214,
  sku: 'BAT-5', marque: '', description: '', garantie: '',
  prix_vente: '7200', prix_achat: '0', tva: 20, quantite_stock: 3, seuil_alerte: 0,
  categorie: null, fournisseur: null,
}
const CLES_MAITRES = [
  ...Object.keys(contrat.exemple_corps_patch), 'paliers_prix_vente',
  ...contrat.cles_nouvelles_astk214,
]

async function ouvrir(produit = BATTERIE) {
  render(<ProduitForm produit={produit} onClose={() => {}} onSaved={() => {}} />,
    { wrapper: wrapperProduitForm })
  await screen.findByText('Données maîtres')
  await waitFor(() => expect(reseau.options).toHaveBeenCalledWith('/stock/produits/'))
}

const enregistrer = () => fireEvent.click(screen.getByRole('button', { name: 'Mettre à jour' }))
const dernierPatch = () => espionsStock.updateProduitApi.mock.calls.at(-1)[1]

beforeEach(() => {
  vi.clearAllMocks()
  reseau.options.mockResolvedValue({ data: OPTIONS_PRODUIT })
  espionsStock.getFichesTechniques.mockResolvedValue({ data: [] })
  espionsStock.updateProduitApi.mockImplementation((id, data) => Promise.resolve({ data: { id, ...data } }))
})

describe('ASTK230 — champs maîtres saisissables', () => {
  it('saisir rôle de devis et unité', async () => {
    await ouvrir()
    // Les choix du rôle viennent de la réponse OPTIONS du serveur.
    expect(await screen.findByRole('option', { name: 'panneau' })).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Rôle de devis'), { target: { value: 'panneau' } })
    fireEvent.change(screen.getByLabelText('Unité de stock'), { target: { value: 'm' } })
    enregistrer()
    await waitFor(() => expect(espionsStock.updateProduitApi).toHaveBeenCalled())
    expect(dernierPatch()).toMatchObject({ role_devis: 'panneau', unite_stock: 'm' })
  })

  it('cocher récurrent et choisir la périodicité', async () => {
    await ouvrir({ ...BATTERIE, est_recurrent: false, periodicite_defaut: null })
    fireEvent.click(screen.getByRole('switch', { name: 'Produit récurrent (abonnement)' }))
    fireEvent.change(screen.getByLabelText('Périodicité par défaut'), { target: { value: 'mensuel' } })
    fireEvent.change(screen.getByLabelText('Classe de danger'), { target: { value: 'INFLAMMABLE' } })
    fireEvent.change(screen.getByLabelText('Tarif location / jour'), { target: { value: '150.00' } })
    enregistrer()
    await waitFor(() => expect(espionsStock.updateProduitApi).toHaveBeenCalled())
    expect(dernierPatch()).toMatchObject({
      est_recurrent: true, periodicite_defaut: 'mensuel',
      classe_danger: 'INFLAMMABLE', tarif_location_jour: '150.00',
    })
  })

  it("enregistrer sans toucher n'envoie aucun champ modifié", async () => {
    await ouvrir()
    // Les valeurs serveur sont relues dans les champs.
    expect(screen.getByLabelText('Code-barres')).toHaveValue(contrat.exemple.code_barres)
    expect(screen.getByLabelText('Code SH')).toHaveValue(contrat.exemple.code_sh)
    expect(screen.getByLabelText('Rôle de devis')).toHaveValue(contrat.exemple.role_devis)
    enregistrer()
    await waitFor(() => expect(espionsStock.updateProduitApi).toHaveBeenCalled())
    const patch = dernierPatch()
    for (const cle of CLES_MAITRES) expect(patch).not.toHaveProperty(cle)
  })

  it('un palier modifié part au format serveur', async () => {
    await ouvrir()
    fireEvent.change(screen.getByLabelText('Palier 2 — prix TTC'), { target: { value: '6800.00' } })
    enregistrer()
    await waitFor(() => expect(espionsStock.updateProduitApi).toHaveBeenCalled())
    expect(dernierPatch().paliers_prix_vente).toEqual([
      { seuil_min: 1, seuil_max: 9, prix_vente_ttc: '7200.00' },
      { seuil_min: 10, seuil_max: null, prix_vente_ttc: '6800.00' },
    ])
  })

  it('un 400 serveur (choix invalide) s\'affiche sous le champ', async () => {
    espionsStock.updateProduitApi.mockRejectedValueOnce({
      response: { status: 400, data: { error: 'x', tarif_location_jour: ['Le tarif de location ne peut pas être négatif.'] } },
    })
    await ouvrir()
    fireEvent.change(screen.getByLabelText('Tarif location / jour'), { target: { value: '-1' } })
    enregistrer()
    expect(await screen.findByText('Le tarif de location ne peut pas être négatif.')).toBeInTheDocument()
  })
})
