import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { documentContrat } from '../../test/fixtures/contractSamples'
import { produitCiACompleter, raisonCiACompleter } from '../../features/stock/catalogue.js'

/* ============================================================================
   CIQ104 — fiche produit : « Usage C&I » (rôle C&I, type de pose, délai
   d'appro) et blocs de fiche C&I. Contrat partagé : produit_ci.json — LU dans
   le fichier (PACT10), jamais recopié. Même harnais que ProduitForm.pompage. */

const contrat = documentContrat('stock', 'produit_ci')

// La réponse OPTIONS du serveur : les choix de `role_ci` / `type_pose` portent
// les libellés FR du contrat (servis par l'API, aucun miroir JS).
const OPTIONS = {
  actions: {
    POST: {
      role_ci: {
        choices: Object.entries(contrat.roles_ci)
          .map(([value, display_name]) => ({ value, display_name })),
      },
      type_pose: {
        choices: contrat.champs_produit.type_pose.choix
          .map((value) => ({ value, display_name: value })),
      },
    },
  },
}

const { apiPost, apiGet, apiOptions } = vi.hoisted(() => ({
  apiPost: vi.fn(),
  apiGet: vi.fn(() => Promise.resolve({ data: [] })),
  apiOptions: vi.fn(),
}))

vi.mock('../../api/axios', () => ({
  default: {
    get: (...args) => apiGet(...args),
    post: (...args) => apiPost(...args),
    options: (...args) => apiOptions(...args),
  },
}))

vi.mock('../../ui', async (importActual) => (
  (await import('../../test/fixtures/produitFormHarness.jsx')).uiAvecSelectNatif(await importActual())
))

vi.mock('../../api/stockApi', async () => ({
  default: (await import('../../test/fixtures/produitFormHarness.jsx')).stockApiSimule(),
}))

import ProduitForm from './ProduitForm.jsx'
import {
  wrapperProduitForm as wrapper, espionsStock,
} from '../../test/fixtures/produitFormHarness.jsx'

const {
  getFichesTechniques, createFicheTechnique, updateFicheTechnique, updateProduitApi,
} = espionsStock

// Le contrôleur d'injection tel que le serveur le sert : clés de `exemple`
// (détail produit) du contrat, rôle C&I posé.
const CONTROLEUR = {
  ...contrat.exemple,
  id: 9, nom: "Contrôleur d'injection C&I", marque: '', role_devis: null,
  role_ci: 'controleur_injection', sku: 'CI-CTRL-INJ', description: '', garantie: '',
  prix_vente: '4000', prix_achat: '0', tva: 20, quantite_stock: 2, seuil_alerte: 0,
  categorie: null, fournisseur: null,
}
// La fiche limiteur telle que le contrat la décrit (vide = non publié).
const FICHE_LIMITEUR = { id: 77, produit: 9, ...contrat.fiches.limiteur.exemple }
const CLES_LIMITEUR = Object.keys(contrat.fiches.limiteur.champs)

function renderEdit(over = {}) {
  return render(
    <ProduitForm produit={{ ...CONTROLEUR, ...over }} onClose={() => {}} onSaved={() => {}} />,
    { wrapper },
  )
}

async function pret() {
  await screen.findByText(/Éditer/)
  await waitFor(() => expect(getFichesTechniques).toHaveBeenCalled())
  await screen.findByText('Usage C&I')
}

beforeEach(() => {
  vi.clearAllMocks()
  apiGet.mockResolvedValue({ data: [] })
  apiOptions.mockResolvedValue({ data: OPTIONS })
  getFichesTechniques.mockResolvedValue({ data: [FICHE_LIMITEUR] })
  createFicheTechnique.mockResolvedValue({ data: { id: 501 } })
  updateFicheTechnique.mockResolvedValue({ data: {} })
  updateProduitApi.mockImplementation((id, data) => Promise.resolve({ data: { id, ...data } }))
})

describe('CIQ104 — rôle C&I et fiche limiteur', () => {
  it('les libellés de rôle viennent de la réponse OPTIONS du serveur', async () => {
    renderEdit()
    await pret()
    await waitFor(() => expect(apiOptions).toHaveBeenCalledWith('/stock/produits/'))
    expect(await screen.findByRole('option', { name: contrat.roles_ci.controleur_injection }))
      .toBeInTheDocument()
  })

  it('role_ci=controleur_injection + lim_onduleurs_max=10 → PATCH conforme au contrat', async () => {
    renderEdit()
    await pret()
    const champ = await screen.findByLabelText("Nombre d'onduleurs pilotés")
    expect(champ).toHaveAttribute('step', 'any')
    fireEvent.change(champ, { target: { value: '10' } })
    fireEvent.click(screen.getByRole('button', { name: 'Mettre à jour' }))
    await waitFor(() => expect(updateFicheTechnique).toHaveBeenCalled())
    const [id, patch] = updateFicheTechnique.mock.calls.at(-1)
    expect(id).toBe(77)
    expect(patch).toEqual({ lim_onduleurs_max: 10 })
    for (const cle of Object.keys(patch)) expect(CLES_LIMITEUR).toContain(cle)
    const [, payload] = updateProduitApi.mock.calls[0]
    expect(payload.role_ci).toBe('controleur_injection')
    expect(payload).not.toHaveProperty('prix_achat_ci')
  })

  it('enregistrer → rouvrir → enregistrer sans toucher = aucun PATCH de fiche', async () => {
    renderEdit()
    await pret()
    await screen.findByLabelText("Nombre d'onduleurs pilotés")
    fireEvent.click(screen.getByRole('button', { name: 'Mettre à jour' }))
    await waitFor(() => expect(updateProduitApi).toHaveBeenCalledTimes(1))
    expect(updateFicheTechnique).not.toHaveBeenCalled()
    expect(createFicheTechnique).not.toHaveBeenCalled()
    const [, payload] = updateProduitApi.mock.calls[0]
    expect(payload.role_ci).toBe(CONTROLEUR.role_ci)
    expect(payload.type_pose).toBe(CONTROLEUR.type_pose)
    expect(payload.delai_appro_jours).toBeNull()
  })

  it('aucune valeur pré-remplie : la fiche servie vide reste vide', async () => {
    renderEdit()
    await pret()
    expect(await screen.findByLabelText("Nombre d'onduleurs pilotés")).toHaveValue(null)
    expect(screen.getByLabelText('Courant maxi en direct (A)')).toHaveValue(null)
  })
})

describe('CIQ104 — onduleur exclu et filtre « C&I à compléter »', () => {
  const exemples = contrat.element_produits_ci.exemples
  const exclu = {
    ...exemples[0], eligible_ci: false,
    motif_exclusion: 'fiche incomplète : courant maxi par MPPT (A)',
  }

  it("un onduleur exclu affiche son motif sur la fiche produit", async () => {
    renderEdit({
      nom: exclu.nom, role_ci: 'onduleur_string_tri',
      etat_ci: {
        role_ci: exclu.role_ci, libelle: contrat.roles_ci.onduleur_string_tri,
        classement: exclu.classement, prix_connu: true,
        eligible_ci: false, motif_exclusion: exclu.motif_exclusion,
      },
    })
    await pret()
    expect(screen.getByText(/Exclu du dimensionnement C&I/))
      .toHaveTextContent(exclu.motif_exclusion)
  })

  it('le filtre lit eligible_ci / motif_exclusion / prix_connu', () => {
    const ok = { etat_ci: { prix_connu: true, eligible_ci: true, motif_exclusion: null } }
    const sansPrix = { etat_ci: { prix_connu: exemples[2].prix_connu, eligible_ci: true, motif_exclusion: null } }
    const exc = { etat_ci: { prix_connu: true, eligible_ci: false, motif_exclusion: exclu.motif_exclusion } }
    expect(produitCiACompleter(ok)).toBe(false)
    expect(produitCiACompleter(sansPrix)).toBe(true)
    expect(raisonCiACompleter(sansPrix)).toBe('prix à renseigner')
    expect(produitCiACompleter(exc)).toBe(true)
    expect(raisonCiACompleter(exc)).toBe(exclu.motif_exclusion)
    expect(produitCiACompleter({ etat_ci: null })).toBe(false)
  })
})
