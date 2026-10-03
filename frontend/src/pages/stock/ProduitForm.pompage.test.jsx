import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import contratPompage from '../../../../backend/django_core/apps/stock/contract_samples/produit_pompage.json'

/* ============================================================================
   AGR105 — fiche produit : champs pompage (rôle, type, alimentation,
   provenance de la courbe, fréquence), fiche pompe / variateur et courbe
   vérifiée cellule par cellule (règle AGR102).
   Contrat partagé : produit_pompage.json (importé, jamais ré-inventé).
   Même harnais que ProduitForm.calx355FicheChamps.test.jsx. */

const { apiPost, apiGet } = vi.hoisted(() => ({
  apiPost: vi.fn(),
  apiGet: vi.fn(() => Promise.resolve({ data: [] })),
}))

vi.mock('../../api/axios', () => ({
  default: { get: (...args) => apiGet(...args), post: (...args) => apiPost(...args) },
}))

vi.mock('../../ui', async (importActual) => {
  const actual = await importActual()
  const Passthrough = ({ children }) => <>{children}</>
  const Select = ({ value, onValueChange, children }) => {
    const kids = Array.isArray(children) ? children : [children]
    const trigger = kids.find((k) => k?.props?.id)
    return (
      <select id={trigger?.props?.id} value={value} onChange={(e) => onValueChange(e.target.value)}>
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

// Un produit pompe tel que le serveur le sert (clés du contrat produit_pompage.json).
const POMPE = {
  id: 7, nom: 'Électropompe submersible 4 pouces', sku: 'PMP-X', marque: '',
  description: '', garantie: '', prix_vente: '5000', prix_achat: '3000', tva: 20,
  quantite_stock: 3, seuil_alerte: 1, categorie: null, fournisseur: null,
  specs_solaire: undefined,
  role_pompage: 'pompe', type_pompe: 'immergee', alimentation: 'tri',
  pompe_cv: '10.00', pompe_kw: '7.50', tension_v: 380,
  courbe_pompe: { debits_m3h: [0, 12, 24], hmt_m: [91, 85, 70] },
  courbe_source: { document: 'Fiche OSP 30', date: '2026-01-15', page: 4 },
  courbe_frequence_hz: 50,
}

const CLES_POMPAGE = [
  'role_pompage', 'type_pompe', 'alimentation', 'courbe_source',
  'courbe_frequence_hz', 'courbe_pompe',
]

function renderEdit(over = {}) {
  return render(
    <ProduitForm produit={{ ...POMPE, ...over }} onClose={() => {}} onSaved={() => {}} />,
    { wrapper },
  )
}

async function pret() {
  await screen.findByText(/Éditer/)
  await waitFor(() => expect(getFichesTechniques).toHaveBeenCalled())
  await screen.findByText('Pompage')
}

beforeEach(() => {
  vi.clearAllMocks()
  apiGet.mockResolvedValue({ data: [] })
  getFichesTechniques.mockResolvedValue({ data: [] })
  createFicheTechnique.mockResolvedValue({ data: { id: 501 } })
  updateFicheTechnique.mockResolvedValue({ data: {} })
  updateProduitApi.mockImplementation((id, data) => Promise.resolve({ data: { id, ...data } }))
})

describe('AGR105 — libellés honnêtes et unités', () => {
  it("« HMT d'arrêt » et « Débit indicatif (non garanti) » remplacent les anciens libellés", async () => {
    renderEdit()
    await pret()
    expect(screen.getByLabelText("HMT d'arrêt (m)")).toBeInTheDocument()
    expect(screen.getByLabelText('Débit indicatif (non garanti) (m³/j)')).toBeInTheDocument()
    expect(screen.queryByLabelText('HMT max (m)')).not.toBeInTheDocument()
    expect(screen.getByText(/Courbe constructeur \(débit m³\/h → HMT m\)/)).toBeInTheDocument()
    expect(screen.getByLabelText('Fréquence de référence de la courbe (Hz)')).toBeInTheDocument()
  })

  it('le vocabulaire des rôles affiché = celui du contrat', async () => {
    renderEdit()
    await pret()
    const select = screen.getByLabelText('Rôle pompage')
    const libelles = [...select.querySelectorAll('option')].map((o) => o.textContent)
    for (const libelle of Object.values(contratPompage.roles_pompage)) {
      expect(libelles).toContain(libelle)
    }
  })
})

describe('AGR105 — courbe vérifiée cellule par cellule', () => {
  it('débits [0, 12, 10] : erreur SOUS la cellule 3, aucun envoi', async () => {
    renderEdit({ courbe_pompe: { debits_m3h: [0, 12, 10], hmt_m: [91, 85, 70] } })
    await pret()
    fireEvent.click(screen.getByRole('button', { name: 'Mettre à jour' }))

    const cellule = screen.getByLabelText('Débit point 3')
    expect(cellule).toHaveAttribute('aria-invalid', 'true')
    const erreur = document.getElementById(cellule.getAttribute('aria-describedby'))
    expect(erreur).toHaveTextContent(/strictement croissants/)
    expect(screen.getByLabelText('Débit point 2')).not.toHaveAttribute('aria-invalid')
    expect(screen.getByTestId('pf-courbe-pompe-bandeau')).toHaveTextContent(/point 3/)
    expect(updateProduitApi).not.toHaveBeenCalled()

    // Corrigée : l'erreur disparaît en direct et l'envoi redevient possible.
    fireEvent.change(cellule, { target: { value: '24' } })
    expect(cellule).not.toHaveAttribute('aria-invalid')
    fireEvent.click(screen.getByRole('button', { name: 'Mettre à jour' }))
    await waitFor(() => expect(updateProduitApi).toHaveBeenCalled())
  })

  it('HMT croissante : erreur sous la cellule HMT fautive', async () => {
    renderEdit({ courbe_pompe: { debits_m3h: [0, 12, 24], hmt_m: [80, 85, 60] } })
    await pret()
    fireEvent.click(screen.getByRole('button', { name: 'Mettre à jour' }))
    const cellule = screen.getByLabelText('HMT point 2')
    expect(cellule).toHaveAttribute('aria-invalid', 'true')
    expect(document.getElementById(cellule.getAttribute('aria-describedby')))
      .toHaveTextContent(/non croissante/)
    expect(updateProduitApi).not.toHaveBeenCalled()
  })

  it('valeur négative : refusée sous sa cellule', async () => {
    renderEdit({ courbe_pompe: { debits_m3h: [0, 12, 24], hmt_m: [80, 70, -1] } })
    await pret()
    fireEvent.click(screen.getByRole('button', { name: 'Mettre à jour' }))
    expect(screen.getByLabelText('HMT point 3')).toHaveAttribute('aria-invalid', 'true')
    expect(updateProduitApi).not.toHaveBeenCalled()
  })
})

describe('AGR105 — enregistrer → rouvrir → enregistrer sans toucher', () => {
  it('le payload pompage est identique à chaque passage, aux valeurs serveur près', async () => {
    const premier = renderEdit()
    await pret()
    fireEvent.click(screen.getByRole('button', { name: 'Mettre à jour' }))
    await waitFor(() => expect(updateProduitApi).toHaveBeenCalledTimes(1))
    const [, payload1] = updateProduitApi.mock.calls[0]
    // Les valeurs saisies reviennent telles quelles (aucun arrondi, aucun défaut).
    expect(payload1.role_pompage).toBe('pompe')
    expect(payload1.type_pompe).toBe('immergee')
    expect(payload1.alimentation).toBe('tri')
    expect(payload1.courbe_frequence_hz).toBe(50)
    expect(payload1.courbe_source).toEqual({ document: 'Fiche OSP 30', date: '2026-01-15', page: 4 })
    expect(payload1.courbe_pompe).toEqual({ debits_m3h: [0, 12, 24], hmt_m: [91, 85, 70] })

    // « Rouvrir » : le formulaire reçoit ce que le serveur renvoie, puis resauvegarde.
    const serveur = {}
    for (const cle of CLES_POMPAGE) serveur[cle] = payload1[cle]
    premier.unmount()
    vi.clearAllMocks()
    updateProduitApi.mockImplementation((id, data) => Promise.resolve({ data: { id, ...data } }))
    getFichesTechniques.mockResolvedValue({ data: [] })
    renderEdit(serveur)
    await pret()
    fireEvent.click(screen.getByRole('button', { name: 'Mettre à jour' }))
    await waitFor(() => expect(updateProduitApi).toHaveBeenCalledTimes(1))
    const [, payload2] = updateProduitApi.mock.calls[0]
    for (const cle of CLES_POMPAGE) expect(payload2[cle]).toEqual(payload1[cle])
  })

  it('un produit sans rien de saisi part à « non publié » : "" et null, jamais 0', async () => {
    renderEdit({
      role_pompage: '', type_pompe: '', alimentation: '', courbe_pompe: null,
      courbe_frequence_hz: null, courbe_source: { document: '', date: null, page: null },
      nom: 'Panneau JA Solar 550W',
    })
    await screen.findByText('Pompage')
    fireEvent.click(screen.getByRole('button', { name: 'Mettre à jour' }))
    await waitFor(() => expect(updateProduitApi).toHaveBeenCalled())
    const [, payload] = updateProduitApi.mock.calls[0]
    expect(payload.role_pompage).toBe('')
    expect(payload.courbe_frequence_hz).toBeNull()
    expect(payload.courbe_source).toEqual({ document: '', date: null, page: null })
  })
})

describe('AGR105 — fiche pompe / variateur de pompage', () => {
  it('rôle « variateur de pompage » : fiche variateur saisissable, un champ vide part à null', async () => {
    renderEdit({
      nom: 'VARIATEUR VEICHI SI23 5.5KW 380V', role_pompage: 'variateur_pompage',
      type_pompe: '', courbe_pompe: null,
    })
    await pret()
    fireEvent.change(screen.getByLabelText('Tension de sortie vers la pompe (V)'), { target: { value: '380' } })
    fireEvent.click(screen.getByRole('button', { name: 'Mettre à jour' }))

    await waitFor(() => expect(createFicheTechnique).toHaveBeenCalled())
    const [payload] = createFicheTechnique.mock.calls[0]
    expect(payload.type_fiche).toBe('variateur_pompage')
    expect(payload.var_v_sortie_v).toBe(380)
    expect(payload.var_voc_reco_min_v).toBeNull()
    expect(payload.var_protection_marche_a_sec).toBeNull()
    for (const cle of Object.keys(contratPompage.fiches.variateur_pompage.champs)) {
      expect(payload).toHaveProperty(cle)
    }
  })

  it('rôle « pompe » : fiche pompe saisissable (nombre d’étages en entier)', async () => {
    renderEdit()
    await pret()
    fireEvent.change(screen.getByLabelText("Nombre d'étages"), { target: { value: '12' } })
    fireEvent.click(screen.getByRole('button', { name: 'Mettre à jour' }))
    await waitFor(() => expect(createFicheTechnique).toHaveBeenCalled())
    const [payload] = createFicheTechnique.mock.calls[0]
    expect(payload.type_fiche).toBe('pompe')
    expect(payload.pompe_nb_etages).toBe(12)
    expect(payload.pompe_i_nominal_a).toBeNull()
  })

  it('une fiche variateur enregistrée est rechargée (booléen oui/non conservé)', async () => {
    getFichesTechniques.mockResolvedValue({ data: [{
      id: 501, produit: 7, type_fiche: 'variateur_pompage',
      var_protection_marche_a_sec: false, var_v_sortie_v: '380.0',
    }] })
    renderEdit({ nom: 'VARIATEUR VEICHI SI23 5.5KW 380V', role_pompage: 'variateur_pompage', courbe_pompe: null })
    await pret()
    await waitFor(() => expect(screen.getByLabelText('Tension de sortie vers la pompe (V)')).toHaveValue(380))
    expect(screen.getByLabelText('Protection marche à sec intégrée')).toHaveValue('non')
    fireEvent.click(screen.getByRole('button', { name: 'Mettre à jour' }))
    await waitFor(() => expect(updateFicheTechnique).toHaveBeenCalled())
    const [id, payload] = updateFicheTechnique.mock.calls[0]
    expect(id).toBe(501)
    expect(payload.var_protection_marche_a_sec).toBe(false)
  })
})
