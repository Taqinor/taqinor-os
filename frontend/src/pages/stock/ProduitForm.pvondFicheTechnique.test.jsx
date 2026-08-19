import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* ============================================================================
   PVOND (fondateur 18/08) — section « Fiche technique » de ProduitForm.jsx.
   ----------------------------------------------------------------------------
   Objectif fondateur : compléter la fiche technique d'un onduleur (ou d'un
   panneau/d'une batterie) depuis Stock doit être une tâche de 2 minutes —
   PAS la chasse au trésor d'aujourd'hui (la promesse de ProduitDetail.jsx,
   « se modifie depuis l'édition du produit », n'était encore tenue nulle
   part). Vérifie : (a) la section apparaît par TYPE, auto-détecté depuis le
   nom tapé ; (b) l'indicateur de complétude (« Chiffrable ✓ » / « Non
   chiffrable — il manque : … ») est l'exact miroir du contrat PVOND et se
   met à jour EN LOCAL, live, pendant la frappe ; (c) l'enregistrement écrit
   la FicheTechnique en second temps (même patron que la photo APX18) sans
   jamais perdre le produit si cet appel échoue.

   NOTE — vitest ne peut pas s'exécuter dans ce worktree (pas de
   node_modules) : ce fichier suit les conventions de ProduitForm.test.jsx et
   n'a été vérifié qu'à la syntaxe (esbuild --jsx=automatic). Le CI normal
   l'exécutera réellement. La logique PURE sous-jacente
   (pvondFicheTechnique.js) EST exécutée par pvondFicheTechnique.test.mjs
   (node --test, sans dépendance). */

const { apiPost, apiGet } = vi.hoisted(() => ({
  apiPost: vi.fn(),
  apiGet: vi.fn(() => Promise.resolve({ data: [] })),
}))

vi.mock('../../api/axios', () => ({
  default: { get: (...args) => apiGet(...args), post: (...args) => apiPost(...args) },
}))

// Radix Select ne s'ouvre pas de façon fiable sous jsdom (portail + pointer
// events) — pattern établi (pages/ventes/ListesPrixPage.test.jsx,
// pages/monitoring/ClientPortalPage.test.jsx) : remplacer les primitives
// Select par un <select> natif. ProduitForm.jsx pose toujours l'`id` sur
// <SelectTrigger> (jamais sur <Select> lui-même — Radix Select.Root ne rend
// aucun nœud DOM propre) ; on le repêche depuis les enfants pour que
// `getByLabelText` (association <label htmlFor>, posée par FormField)
// continue de fonctionner SANS toucher au code de production.
vi.mock('../../ui', async (importActual) => {
  const actual = await importActual()
  const Passthrough = ({ children }) => <>{children}</>
  const Select = ({ value, onValueChange, children }) => {
    const kids = Array.isArray(children) ? children : [children]
    const trigger = kids.find((k) => k?.props?.id)
    return (
      <select
        id={trigger?.props?.id}
        value={value}
        onChange={(e) => onValueChange(e.target.value)}
      >
        {kids}
      </select>
    )
  }
  return {
    ...actual,
    Select,
    SelectTrigger: Passthrough,
    SelectValue: () => null,
    SelectContent: Passthrough,
    SelectItem: ({ value, children }) => <option value={value}>{children}</option>,
  }
})

const {
  getFichesTechniques, createFicheTechnique, updateFicheTechnique,
  createProduitApi, updateProduitApi,
} = vi.hoisted(() => ({
  getFichesTechniques: vi.fn(() => Promise.resolve({ data: [] })),
  createFicheTechnique: vi.fn(() => Promise.resolve({ data: { id: 501 } })),
  updateFicheTechnique: vi.fn(() => Promise.resolve({ data: {} })),
  // `stockSlice.createProduit`/`updateProduit` (createAsyncThunk RÉELS, non
  // mockés) appellent `stockApi.createProduit`/`stockApi.updateProduit` — les
  // stubber ICI suffit, pas besoin de mocker le slice.
  createProduitApi: vi.fn((data) => Promise.resolve({ data: { id: 42, ...data } })),
  updateProduitApi: vi.fn((id, data) => Promise.resolve({ data: { id, ...data } })),
}))

vi.mock('../../api/stockApi', () => ({
  default: {
    getProduitPrixFournisseurs: () => Promise.resolve({ data: [] }),
    comparerFournisseurs: () => Promise.resolve({ data: [] }),
    comparerTcoFournisseurs: () => Promise.resolve({ data: { fournisseurs: [] } }),
    createPrixFournisseur: () => Promise.resolve({ data: {} }),
    updatePrixFournisseur: () => Promise.resolve({ data: {} }),
    deletePrixFournisseur: () => Promise.resolve({ data: {} }),
    uploadProduitImage: () => Promise.resolve({ data: {} }),
    getFichesTechniques: (...args) => getFichesTechniques(...args),
    createFicheTechnique: (...args) => createFicheTechnique(...args),
    updateFicheTechnique: (...args) => updateFicheTechnique(...args),
    createProduit: (...args) => createProduitApi(...args),
    updateProduit: (...args) => updateProduitApi(...args),
  },
}))

import ProduitForm from './ProduitForm.jsx'

const store = configureStore({
  reducer: {
    auth: (s = { role: 'admin', role_nom: 'Directeur', permissions: [] }) => s,
    stock: (s = { categories: [], fournisseurs: [], produits: [] }) => s,
  },
})

function wrapper({ children }) {
  return (
    <Provider store={store}>
      <MemoryRouter><ThemeProvider>{children}</ThemeProvider></MemoryRouter>
    </Provider>
  )
}

const ONDULEUR = {
  id: 7, nom: 'Onduleur hybride Deye 8kW', sku: 'OND-DEYE-8K', marque: 'Deye',
  description: '', garantie: '', prix_vente: '14000', prix_achat: '9000', tva: 20,
  quantite_stock: 3, seuil_alerte: 1, categorie: null, fournisseur: null,
  specs_solaire: { famille: 'onduleur', plage_batterie_v: null, v_nominal: null, manquantes: [] },
}

function renderEdit(over = {}) {
  return render(
    <ProduitForm produit={{ ...ONDULEUR, ...over }} onClose={() => {}} onSaved={() => {}} />,
    { wrapper },
  )
}

function renderCreate() {
  return render(<ProduitForm produit={null} onClose={() => {}} onSaved={() => {}} />, { wrapper })
}

beforeEach(() => {
  vi.clearAllMocks()
  apiGet.mockResolvedValue({ data: [] })
  getFichesTechniques.mockResolvedValue({ data: [] })
  createFicheTechnique.mockResolvedValue({ data: { id: 501 } })
  updateFicheTechnique.mockResolvedValue({ data: {} })
})

describe('ProduitForm — section « Fiche technique » (PVOND)', () => {
  it('n\'affiche AUCUNE section pour un produit non classifié (ex. structure générique)', async () => {
    renderEdit({ nom: 'Vis inox M8 (boîte de 100)' })
    await screen.findByText(/Éditer/)
    expect(screen.queryByText('Fiche technique')).not.toBeInTheDocument()
  })

  it('affiche les champs ONDULEUR et l\'indicateur « Non chiffrable » quand tout manque', async () => {
    renderEdit()
    await screen.findByText(/Éditer/)
    await waitFor(() => expect(getFichesTechniques).toHaveBeenCalledWith(7))
    expect(await screen.findByText('Fiche technique')).toBeInTheDocument()
    expect(screen.getByLabelText('Puissance AC (kW)')).toBeInTheDocument()
    expect(screen.getByLabelText("Nombre d'entrées MPPT")).toBeInTheDocument()
    expect(screen.getByText(/Non chiffrable — il manque :/)).toBeInTheDocument()
  })

  // PVOND-H (fondateur 19/08/2026) — « have a place for every one of this
  // information » : tension de démarrage et Isc max par MPPT sont désormais
  // éditables, mais restent OPTIONNELLES (le moteur électrique a un repli
  // sûr en leur absence) — jamais comptées dans le badge « Chiffrable ».
  it('les nouveaux champs onduleur (démarrage, Isc max MPPT) sont éditables et OPTIONNELS', async () => {
    renderEdit()
    await screen.findByText(/Éditer/)
    await waitFor(() => expect(getFichesTechniques).toHaveBeenCalled())
    expect(screen.getByLabelText('Tension de démarrage (V)')).toBeInTheDocument()
    expect(screen.getByLabelText('Isc maxi par MPPT (A)')).toBeInTheDocument()
    // Remplir les 8 variables du contrat SANS toucher aux deux nouveaux
    // champs optionnels atteint quand même « Chiffrable ✓ ».
    fireEvent.change(document.getElementById('pf-gar-txt'), { target: { value: 'Garantie constructeur 10 ans' } })
    fireEvent.change(screen.getByLabelText('Puissance AC (kW)'), { target: { value: '8' } })
    fireEvent.change(screen.getByLabelText('Phases'), { target: { value: '3' } })
    fireEvent.change(screen.getByLabelText("Nombre d'entrées MPPT"), { target: { value: '2' } })
    fireEvent.change(screen.getByLabelText('Courant maxi par MPPT (A)'), { target: { value: '26' } })
    fireEvent.change(screen.getByLabelText('Plage MPPT — tension mini (V)'), { target: { value: '200' } })
    fireEvent.change(screen.getByLabelText('Plage MPPT — tension maxi (V)'), { target: { value: '650' } })
    fireEvent.change(screen.getByLabelText('Tension DC maximale (V)'), { target: { value: '800' } })
    fireEvent.change(screen.getByLabelText('Rendement européen (%)'), { target: { value: '97' } })
    fireEvent.click(screen.getByLabelText('Aucune batterie compatible (onduleur réseau)'))

    expect(await screen.findByText('Chiffrable ✓')).toBeInTheDocument()
  })

  it('la plage de tension batterie n\'apparaît que pour un onduleur HYBRIDE', async () => {
    renderEdit({ nom: 'Onduleur réseau Huawei 10kW' })
    await screen.findByText(/Éditer/)
    await screen.findByText('Fiche technique')
    expect(screen.queryByLabelText('Plage batterie — tension mini (V)')).not.toBeInTheDocument()
  })

  it('remplir les champs onduleur éteint « Non chiffrable » et affiche « Chiffrable ✓ »', async () => {
    renderEdit()
    await screen.findByText(/Éditer/)
    await waitFor(() => expect(getFichesTechniques).toHaveBeenCalled())

    // Texte de garantie (section Garantie, déjà existante) : une des 10
    // variables du contrat.
    fireEvent.change(document.getElementById('pf-gar-txt'), { target: { value: 'Garantie constructeur 10 ans' } })
    fireEvent.change(screen.getByLabelText('Puissance AC (kW)'), { target: { value: '8' } })
    // « Phases » est un <Select> (mocké en <select> natif ci-dessus) — 10ᵉ
    // variable du contrat, oubliée dans une version antérieure de ce test :
    // sans elle, « monophasé / triphasé » restait manquant et le badge ne
    // pouvait JAMAIS passer à « Chiffrable ✓ » quoi que fassent les 9 autres
    // champs.
    fireEvent.change(screen.getByLabelText('Phases'), { target: { value: '3' } })
    fireEvent.change(screen.getByLabelText("Nombre d'entrées MPPT"), { target: { value: '2' } })
    fireEvent.change(screen.getByLabelText('Courant maxi par MPPT (A)'), { target: { value: '26' } })
    fireEvent.change(screen.getByLabelText('Plage MPPT — tension mini (V)'), { target: { value: '200' } })
    fireEvent.change(screen.getByLabelText('Plage MPPT — tension maxi (V)'), { target: { value: '650' } })
    fireEvent.change(screen.getByLabelText('Tension DC maximale (V)'), { target: { value: '800' } })
    fireEvent.change(screen.getByLabelText('Rendement européen (%)'), { target: { value: '97' } })
    // Plage batterie (hybride) : « aucune batterie » déclare la variable.
    fireEvent.click(screen.getByLabelText('Aucune batterie compatible (onduleur réseau)'))

    expect(await screen.findByText('Chiffrable ✓')).toBeInTheDocument()
    expect(screen.queryByText(/Non chiffrable/)).not.toBeInTheDocument()
  })

  // PVOND-H (fondateur 19/08/2026) — la plage de tension batterie s'écrit
  // désormais dans le champ DÉDIÉ de FicheTechnique, plus dans une ligne
  // devinée de `Produit.description` : la description reste INTACTE.
  it('la plage de tension batterie s\'écrit dans le champ dédié, jamais dans la description', async () => {
    renderEdit()
    await screen.findByText(/Éditer/)
    await waitFor(() => expect(getFichesTechniques).toHaveBeenCalled())

    fireEvent.change(screen.getByLabelText('Plage batterie — tension mini (V)'), { target: { value: '40' } })
    fireEvent.change(screen.getByLabelText('Plage batterie — tension maxi (V)'), { target: { value: '60' } })

    expect(document.getElementById('pf-desc').value).toBe('')
  })

  it('RÉSEAU : « Chiffrable ✓ » sans jamais avoir à déclarer de plage batterie (règle 18/08, commit ed34ced9)', async () => {
    // Un onduleur RÉSEAU n'a pas de port batterie : sa famille (lue sur le
    // nom, comme `famille_onduleur` côté backend) vaut à elle seule
    // déclaration « aucune » — y compris fraîchement créé, SANS aller-retour
    // serveur (`specs_solaire` absent). Reproduit le bug corrigé de
    // `plageBatterieAbsenteLocale`.
    renderEdit({
      nom: 'Onduleur réseau Huawei 10kW', description: '', garantie: 'Garantie 10 ans',
      specs_solaire: undefined,
    })
    await screen.findByText(/Éditer/)
    await waitFor(() => expect(getFichesTechniques).toHaveBeenCalled())

    fireEvent.change(screen.getByLabelText('Puissance AC (kW)'), { target: { value: '10' } })
    fireEvent.change(screen.getByLabelText('Phases'), { target: { value: '3' } })
    fireEvent.change(screen.getByLabelText("Nombre d'entrées MPPT"), { target: { value: '2' } })
    fireEvent.change(screen.getByLabelText('Courant maxi par MPPT (A)'), { target: { value: '26' } })
    fireEvent.change(screen.getByLabelText('Plage MPPT — tension mini (V)'), { target: { value: '200' } })
    fireEvent.change(screen.getByLabelText('Plage MPPT — tension maxi (V)'), { target: { value: '650' } })
    fireEvent.change(screen.getByLabelText('Tension DC maximale (V)'), { target: { value: '800' } })
    fireEvent.change(screen.getByLabelText('Rendement européen (%)'), { target: { value: '97' } })
    // AUCUNE interaction avec un contrôle « plage batterie » — il n'y en a
    // pas pour un réseau (widget réservé au HYBRIDE, testé plus haut).

    expect(await screen.findByText('Chiffrable ✓')).toBeInTheDocument()
    expect(screen.queryByText(/Non chiffrable/)).not.toBeInTheDocument()
  })

  it('l\'enregistrement écrit la FicheTechnique — MISE À JOUR si elle existe déjà', async () => {
    getFichesTechniques.mockResolvedValue({ data: [{ id: 501, produit: 7, type_fiche: 'onduleur', ond_ac_kw: '8' }] })
    renderEdit()
    await screen.findByText(/Éditer/)
    await waitFor(() => expect(getFichesTechniques).toHaveBeenCalled())

    fireEvent.change(screen.getByLabelText('Puissance AC (kW)'), { target: { value: '10' } })
    fireEvent.click(screen.getByRole('button', { name: 'Mettre à jour' }))

    await waitFor(() => expect(updateProduitApi).toHaveBeenCalled())
    await waitFor(() => expect(updateFicheTechnique).toHaveBeenCalledWith(
      501, expect.objectContaining({ type_fiche: 'onduleur', ond_ac_kw: 10 })))
    expect(createFicheTechnique).not.toHaveBeenCalled()
  })

  it('un échec d\'enregistrement de la fiche NE PERD JAMAIS le produit déjà sauvegardé', async () => {
    updateFicheTechnique.mockRejectedValue({ response: { status: 500 } })
    getFichesTechniques.mockResolvedValue({ data: [{ id: 501, produit: 7, type_fiche: 'onduleur' }] })
    const onSaved = vi.fn()
    render(<ProduitForm produit={ONDULEUR} onClose={() => {}} onSaved={onSaved} />, { wrapper })
    await screen.findByText(/Éditer/)
    await waitFor(() => expect(getFichesTechniques).toHaveBeenCalled())

    fireEvent.change(screen.getByLabelText('Puissance AC (kW)'), { target: { value: '10' } })
    fireEvent.click(screen.getByRole('button', { name: 'Mettre à jour' }))

    await waitFor(() => expect(updateProduitApi).toHaveBeenCalled())
    await waitFor(() => expect(onSaved).toHaveBeenCalled())
  })

  it('rien à écrire (aucun champ, aucune fiche existante) → aucun appel de création', async () => {
    renderEdit()
    await screen.findByText(/Éditer/)
    await waitFor(() => expect(getFichesTechniques).toHaveBeenCalled())

    fireEvent.click(screen.getByRole('button', { name: 'Mettre à jour' }))

    await waitFor(() => expect(updateProduitApi).toHaveBeenCalled())
    expect(createFicheTechnique).not.toHaveBeenCalled()
    expect(updateFicheTechnique).not.toHaveBeenCalled()
  })

  it('type PANNEAU : champs puissance/dimensions, jamais les champs onduleur', async () => {
    renderEdit({ nom: 'Panneau JA Solar 550W', specs_solaire: undefined })
    await screen.findByText(/Éditer/)
    expect(await screen.findByText('Fiche technique')).toBeInTheDocument()
    expect(screen.getByLabelText('Puissance crête (Wc)')).toBeInTheDocument()
    expect(screen.getByLabelText('Longueur (mm)')).toBeInTheDocument()
    expect(screen.queryByLabelText('Puissance AC (kW)')).not.toBeInTheDocument()
  })

  // PVOND-H (fondateur 19/08/2026) — Voc/Isc/Vmp/Imp et les coefficients de
  // température EXISTAIENT déjà sur FicheTechnique (lus par le moteur
  // électrique) mais n'étaient éditables NULLE PART à l'écran.
  it('type PANNEAU : Voc/Isc/Vmp/Imp et coefficients de température sont éditables', async () => {
    renderEdit({ nom: 'Panneau JA Solar 550W', specs_solaire: undefined })
    await screen.findByText(/Éditer/)
    await screen.findByText('Fiche technique')
    expect(screen.getByLabelText('Tension circuit ouvert — Voc (V)')).toBeInTheDocument()
    expect(screen.getByLabelText('Courant court-circuit — Isc (A)')).toBeInTheDocument()
    expect(screen.getByLabelText('Tension au point de puissance max — Vmp (V)')).toBeInTheDocument()
    expect(screen.getByLabelText('Courant au point de puissance max — Imp (A)')).toBeInTheDocument()
    expect(screen.getByLabelText('Coefficient de température Voc (%/°C)')).toBeInTheDocument()
    expect(screen.getByLabelText('Coefficient de température Pmax (%/°C)')).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('Tension circuit ouvert — Voc (V)'), { target: { value: '48.3' } })
    fireEvent.click(screen.getByRole('button', { name: 'Mettre à jour' }))

    await waitFor(() => expect(updateProduitApi).toHaveBeenCalled())
    await waitFor(() => expect(createFicheTechnique).toHaveBeenCalledWith(
      expect.objectContaining({ type_fiche: 'module', voc_v: 48.3 })))
  })

  it('type BATTERIE : capacité/tension/DoD', async () => {
    renderEdit({ nom: 'Batterie lithium 5.12kWh', specs_solaire: undefined })
    await screen.findByText(/Éditer/)
    expect(await screen.findByText('Fiche technique')).toBeInTheDocument()
    expect(screen.getByLabelText('Capacité nominale (kWh)')).toBeInTheDocument()
    expect(screen.getByLabelText('Tension nominale (V)')).toBeInTheDocument()
  })

  it('type POMPE : lecture seule, aucun champ éditable de fiche technique', async () => {
    renderEdit({
      nom: 'Pompe immergée OSP 30/8', specs_solaire: undefined,
      pompe_cv: '10', hmt_m: '91', pompe_kw: '7.5', tension_v: 380,
    })
    await screen.findByText(/Éditer/)
    expect(await screen.findByText('Fiche technique')).toBeInTheDocument()
    expect(screen.getByText('91')).toBeInTheDocument()   // HMT max, lu tel quel
    expect(screen.queryByLabelText('Puissance AC (kW)')).not.toBeInTheDocument()
  })

  it('création : la section apparaît en tapant le nom, avant même d\'enregistrer', async () => {
    renderCreate()
    await screen.findByText('Nouveau produit')
    expect(screen.queryByText('Fiche technique')).not.toBeInTheDocument()
    fireEvent.change(screen.getByPlaceholderText('Nom du produit'), {
      target: { value: 'Onduleur hybride Deye 5kW' },
    })
    expect(await screen.findByText('Fiche technique')).toBeInTheDocument()
    // Aucun appel réseau à l'affichage : pas de produit.id à interroger.
    expect(getFichesTechniques).not.toHaveBeenCalled()
  })
})
