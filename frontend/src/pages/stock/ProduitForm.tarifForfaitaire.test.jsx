import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'

/* ============================================================================
   L-STOCKUI (fondateur 24/08) — bloc « Tarification forfaitaire
   (composition) » de ProduitForm.jsx.
   ----------------------------------------------------------------------------
   Contrat FIXÉ (lane backend séparée, pas touchée ici) : le serializer
   Produit expose `prix_fixe_ht` et `prix_par_panneau_ht` (Decimal nullables,
   lecture/écriture). Vérifie : (a) le bloc est visible sur TOUTE fiche
   produit (aucun filtrage par catégorie — le fondateur décide où il le
   remplit), sur un produit non classifié aussi bien qu'un onduleur ; (b) la
   soumission envoie les deux clés ; (c) un champ laissé vide part en `null`,
   jamais `0` (contrainte explicite de la mission — un forfait à 0 DH n'est
   PAS la même chose qu'« aucune tarification forfaitaire ») ; (d) l'édition
   pré-remplit depuis les valeurs existantes du produit.

   NOTE — vitest ne peut pas s'exécuter dans ce worktree (pas de
   node_modules) : ce fichier suit les conventions de
   ProduitForm.pvondFicheTechnique.test.jsx et n'a été vérifié qu'à la
   syntaxe. Le CI normal l'exécutera réellement. */

vi.mock('../../api/axios', async () => (await import('./ProduitForm.testHelpers.jsx')).axiosMock)
vi.mock('../../ui', async (importActual) => (await import('./ProduitForm.testHelpers.jsx')).uiMock(await importActual()))
vi.mock('../../api/stockApi', async () => (await import('./ProduitForm.testHelpers.jsx')).stockApiMock)

import ProduitForm from './ProduitForm.jsx'
import { getFichesTechniques, createProduitApi, updateProduitApi, wrapper } from './ProduitForm.testHelpers.jsx'

// Produit générique, NON classifié (pas onduleur/panneau/batterie/pompe) —
// le bloc doit rester visible même là où « Fiche technique » ne s'affiche pas.
const PRODUIT_GENERIQUE = {
  id: 9, nom: 'Tableau AC-DC coffret standard', sku: 'TAB-ACDC-1', marque: '',
  description: '', prix_vente: '3200', prix_achat: '1800', tva: 20,
  quantite_stock: 4, seuil_alerte: 1, categorie: null, fournisseur: null,
}

function renderEdit(over = {}) {
  return render(
    <ProduitForm produit={{ ...PRODUIT_GENERIQUE, ...over }} onClose={() => {}} onSaved={() => {}} />,
    { wrapper },
  )
}

function renderCreate() {
  return render(<ProduitForm produit={null} onClose={() => {}} onSaved={() => {}} />, { wrapper })
}

beforeEach(() => {
  vi.clearAllMocks()
  getFichesTechniques.mockResolvedValue({ data: [] })
})

describe('ProduitForm — tarification forfaitaire par composition (L-STOCKUI)', () => {
  it('le bloc est visible sur un produit non classifié (Tableau AC-DC), là où « Fiche technique » ne s\'affiche pas', async () => {
    renderEdit()
    await screen.findByText(/Éditer/)
    expect(screen.queryByText('Fiche technique')).not.toBeInTheDocument()
    const resume = document.getElementById('pf-tarif-summary')
    expect(resume).toHaveTextContent('Tarification forfaitaire (composition)')
    // Repliée par défaut (bloc secondaire) — ouvrir avant de vérifier les
    // champs, comme le ferait un utilisateur. (id stable : le résumé peut
    // aussi porter un suffixe « (renseignée) », cf. test de pré-remplissage.)
    fireEvent.click(resume)
    expect(screen.getByLabelText('Partie fixe (DH HT)')).toBeInTheDocument()
    expect(screen.getByLabelText('Par panneau (DH HT)')).toBeInTheDocument()
  })

  it('le bloc est aussi visible en création, avant tout nom tapé', async () => {
    renderCreate()
    await screen.findByText('Nouveau produit')
    expect(document.getElementById('pf-tarif-summary')).toHaveTextContent('Tarification forfaitaire (composition)')
  })

  it('les deux champs sont vides par défaut (aucune valeur forcée à 0)', async () => {
    renderEdit()
    await screen.findByText(/Éditer/)
    fireEvent.click(document.getElementById('pf-tarif-summary'))
    expect(screen.getByLabelText('Partie fixe (DH HT)')).toHaveValue(null)
    expect(screen.getByLabelText('Par panneau (DH HT)')).toHaveValue(null)
  })

  it('édition : pré-remplit depuis les valeurs existantes du produit, et signale le bloc « renseignée »', async () => {
    renderEdit({ prix_fixe_ht: '1500', prix_par_panneau_ht: '120.5' })
    await screen.findByText(/Éditer/)
    // Déjà renseigné dès le chargement → le résumé replié le signale, SANS
    // avoir besoin de l'ouvrir pour le savoir.
    expect(document.getElementById('pf-tarif-summary')).toHaveTextContent('(renseignée)')
    // Le bloc est REPLIÉ par défaut (bloc secondaire, ordre fondateur) —
    // l'ouvrir avant toute lecture de valeur, comme le ferait un utilisateur.
    fireEvent.click(document.getElementById('pf-tarif-summary'))
    expect(screen.getByLabelText('Partie fixe (DH HT)')).toHaveValue(1500)
    expect(screen.getByLabelText('Par panneau (DH HT)')).toHaveValue(120.5)
  })

  it('rien de saisi → la soumission envoie `null` pour les deux clés, jamais `0`', async () => {
    renderEdit()
    await screen.findByText(/Éditer/)

    fireEvent.click(screen.getByRole('button', { name: 'Mettre à jour' }))

    await waitFor(() => expect(updateProduitApi).toHaveBeenCalled())
    const [, payload] = updateProduitApi.mock.calls[0]
    expect(payload.prix_fixe_ht).toBeNull()
    expect(payload.prix_par_panneau_ht).toBeNull()
  })

  it('les deux valeurs saisies partent dans le payload de soumission', async () => {
    renderEdit()
    await screen.findByText(/Éditer/)

    fireEvent.click(document.getElementById('pf-tarif-summary'))
    fireEvent.change(screen.getByLabelText('Partie fixe (DH HT)'), { target: { value: '900' } })
    fireEvent.change(screen.getByLabelText('Par panneau (DH HT)'), { target: { value: '75.25' } })
    fireEvent.click(screen.getByRole('button', { name: 'Mettre à jour' }))

    await waitFor(() => expect(updateProduitApi).toHaveBeenCalled())
    const [, payload] = updateProduitApi.mock.calls[0]
    expect(payload.prix_fixe_ht).toBe('900')
    expect(payload.prix_par_panneau_ht).toBe('75.25')
  })

  it('un seul des deux champs renseigné : l\'autre reste `null`', async () => {
    renderEdit()
    await screen.findByText(/Éditer/)

    fireEvent.click(document.getElementById('pf-tarif-summary'))
    fireEvent.change(screen.getByLabelText('Partie fixe (DH HT)'), { target: { value: '400' } })
    fireEvent.click(screen.getByRole('button', { name: 'Mettre à jour' }))

    await waitFor(() => expect(updateProduitApi).toHaveBeenCalled())
    const [, payload] = updateProduitApi.mock.calls[0]
    expect(payload.prix_fixe_ht).toBe('400')
    expect(payload.prix_par_panneau_ht).toBeNull()
  })

  it('création : les deux clés partent aussi (vides → null)', async () => {
    renderCreate()
    await screen.findByText('Nouveau produit')

    fireEvent.change(screen.getByPlaceholderText('Nom du produit'), { target: { value: 'Structure au sol' } })
    // Ciblage par id (même contournement que pf-tarif-summary plus haut) :
    // en mode création l'association label/champ ne résout pas sous jsdom.
    fireEvent.change(document.getElementById('pf-vente'), { target: { value: '500' } })
    fireEvent.click(screen.getByRole('button', { name: 'Créer le produit' }))

    await waitFor(() => expect(createProduitApi).toHaveBeenCalled())
    const [payload] = createProduitApi.mock.calls[0]
    expect(payload.prix_fixe_ht).toBeNull()
    expect(payload.prix_par_panneau_ht).toBeNull()
  })
})
