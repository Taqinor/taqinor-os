import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* ============================================================================
   CALX355 — les nouveaux champs de fiche SAISISSABLES dans ProduitForm.jsx.
   ----------------------------------------------------------------------------
   Parité PV*SOL (dialogue de création par champ, modèle de charge partielle
   inclus). Vérifie : (a) les blocs MODULE (NOCT, bifacialité, tolérance,
   courbe rendement/irradiance), ONDULEUR (rendement maximal, CEC, courbe),
   BATTERIE (C-rate, chimie, plage de température) et OPTIMISEUR (sortie) sont
   à l'écran ; (b) un champ vide reste vide et n'est JAMAIS envoyé à 0 ;
   (c) la courbe se saisit et se supprime ligne par ligne, et chaque ligne
   nomme son erreur sous la cellule fautive — le bandeau la nomme aussi et
   rien n'est enregistré tant qu'elle est fausse.

   Même harnais que ProduitForm.pvondFicheTechnique.test.jsx (Select Radix
   remplacé par un <select> natif, stockApi stubbé). La logique PURE
   (pvondFicheTechnique.js) est exécutée par pvondFicheTechnique.test.mjs
   (node --test, sans dépendance). */

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

const PRODUIT = {
  id: 7, nom: 'Panneau JA Solar 550W', sku: 'PAN-JA-550', marque: 'JA Solar',
  description: '', garantie: '', prix_vente: '1400', prix_achat: '900', tva: 10,
  quantite_stock: 3, seuil_alerte: 1, categorie: null, fournisseur: null,
  specs_solaire: undefined,
}

function renderEdit(over = {}) {
  return render(
    <ProduitForm produit={{ ...PRODUIT, ...over }} onClose={() => {}} onSaved={() => {}} />,
    { wrapper },
  )
}

async function pret() {
  await screen.findByText(/Éditer/)
  await waitFor(() => expect(getFichesTechniques).toHaveBeenCalled())
  await screen.findByText('Fiche technique')
}

beforeEach(() => {
  vi.clearAllMocks()
  apiGet.mockResolvedValue({ data: [] })
  getFichesTechniques.mockResolvedValue({ data: [] })
  createFicheTechnique.mockResolvedValue({ data: { id: 501 } })
  updateFicheTechnique.mockResolvedValue({ data: {} })
})

describe('CALX355 — bloc MODULE', () => {
  it('NOCT, bifacialité, tolérance et courbe sont saisissables ; un champ vide part à null, jamais 0', async () => {
    renderEdit()
    await pret()
    expect(screen.getByLabelText('NOCT — température nominale de fonctionnement (°C)')).toBeInTheDocument()
    expect(screen.getByLabelText('Facteur de bifacialité (%)')).toBeInTheDocument()
    expect(screen.getByLabelText('Tolérance de puissance — borne basse (%)')).toBeInTheDocument()
    expect(screen.getByLabelText('Tolérance de puissance — borne haute (%)')).toBeInTheDocument()
    // Les coefficients de température restent saisissables (PVOND-H).
    expect(screen.getByLabelText('Coefficient de température Voc (%/°C)')).toBeInTheDocument()
    expect(screen.getByTestId('pf-courbe-rendement_par_irradiance')).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('Facteur de bifacialité (%)'), { target: { value: '80' } })
    fireEvent.change(screen.getByLabelText('Tolérance de puissance — borne basse (%)'), { target: { value: '-3' } })
    fireEvent.click(screen.getByRole('button', { name: 'Mettre à jour' }))

    await waitFor(() => expect(createFicheTechnique).toHaveBeenCalled())
    const [payload] = createFicheTechnique.mock.calls[0]
    expect(payload.type_fiche).toBe('module')
    expect(payload.bifacialite_pct).toBe(80)
    expect(payload.tolerance_pmax_min_pct).toBe(-3)
    // Vides : null — jamais 0, jamais une courbe vide `[]`.
    expect(payload.noct_c).toBeNull()
    expect(payload.tolerance_pmax_max_pct).toBeNull()
    expect(payload.rendement_par_irradiance).toBeNull()
  })

  it('la courbe se saisit point par point et part en nombres', async () => {
    renderEdit()
    await pret()
    const bloc = screen.getByTestId('pf-courbe-rendement_par_irradiance')
    fireEvent.click(within(bloc).getByRole('button', { name: 'Ajouter un point — Courbe rendement / irradiance' }))
    fireEvent.click(within(bloc).getByRole('button', { name: 'Ajouter un point — Courbe rendement / irradiance' }))
    fireEvent.change(within(bloc).getByLabelText('Irradiance (W/m²) — point 1'), { target: { value: '200' } })
    fireEvent.change(within(bloc).getByLabelText('Rendement relatif (% du STC) — point 1'), { target: { value: '96.5' } })
    fireEvent.change(within(bloc).getByLabelText('Irradiance (W/m²) — point 2'), { target: { value: '1000' } })
    fireEvent.change(within(bloc).getByLabelText('Rendement relatif (% du STC) — point 2'), { target: { value: '100' } })
    fireEvent.click(screen.getByRole('button', { name: 'Mettre à jour' }))

    await waitFor(() => expect(createFicheTechnique).toHaveBeenCalled())
    expect(createFicheTechnique.mock.calls[0][0].rendement_par_irradiance).toEqual([
      { w_m2: 200, rendement_relatif_pct: 96.5 },
      { w_m2: 1000, rendement_relatif_pct: 100 },
    ])
  })

  it('une ligne se SUPPRIME seule ; la dernière supprimée vide la courbe (null)', async () => {
    getFichesTechniques.mockResolvedValue({ data: [{
      id: 501, produit: 7, type_fiche: 'module',
      rendement_par_irradiance: [
        { w_m2: 200, rendement_relatif_pct: 96 },
        { w_m2: 1000, rendement_relatif_pct: 100 },
      ],
    }] })
    renderEdit()
    await pret()
    const bloc = screen.getByTestId('pf-courbe-rendement_par_irradiance')
    // La courbe enregistrée est rechargée ligne par ligne.
    expect(within(bloc).getByLabelText('Irradiance (W/m²) — point 1')).toHaveValue(200)
    expect(within(bloc).getByLabelText('Irradiance (W/m²) — point 2')).toHaveValue(1000)

    fireEvent.click(within(bloc).getByRole('button', { name: 'Retirer le point 1 — Courbe rendement / irradiance' }))
    expect(within(bloc).queryByLabelText('Irradiance (W/m²) — point 2')).not.toBeInTheDocument()
    expect(within(bloc).getByLabelText('Irradiance (W/m²) — point 1')).toHaveValue(1000)

    fireEvent.click(within(bloc).getByRole('button', { name: 'Retirer le point 1 — Courbe rendement / irradiance' }))
    expect(within(bloc).getByText(/Aucun point — courbe non publiée/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Mettre à jour' }))

    await waitFor(() => expect(updateFicheTechnique).toHaveBeenCalled())
    const [id, payload] = updateFicheTechnique.mock.calls[0]
    expect(id).toBe(501)
    expect(payload.rendement_par_irradiance).toBeNull()
  })

  it('une ligne fautive nomme son erreur SOUS la cellule, le bandeau la nomme, rien n’est enregistré', async () => {
    renderEdit()
    await pret()
    const bloc = screen.getByTestId('pf-courbe-rendement_par_irradiance')
    fireEvent.click(within(bloc).getByRole('button', { name: 'Ajouter un point — Courbe rendement / irradiance' }))
    fireEvent.change(within(bloc).getByLabelText('Irradiance (W/m²) — point 1'), { target: { value: '200' } })
    // Rendement relatif laissé vide.
    fireEvent.click(screen.getByRole('button', { name: 'Mettre à jour' }))

    const cellule = within(bloc).getByLabelText('Rendement relatif (% du STC) — point 1')
    expect(cellule).toHaveAttribute('aria-invalid', 'true')
    const idErreur = cellule.getAttribute('aria-describedby')
    expect(document.getElementById(idErreur)).toHaveTextContent(/Valeur requise — Rendement relatif/)
    expect(screen.getByTestId('pf-courbes-bandeau')).toHaveTextContent(/Courbe rendement \/ irradiance/)
    expect(screen.getByTestId('pf-courbes-bandeau')).toHaveTextContent(/point 1/)
    expect(updateProduitApi).not.toHaveBeenCalled()
    expect(createFicheTechnique).not.toHaveBeenCalled()

    // Corrigée : l'erreur et le bandeau disparaissent en direct.
    fireEvent.change(cellule, { target: { value: '96' } })
    expect(screen.queryByTestId('pf-courbes-bandeau')).not.toBeInTheDocument()
    expect(cellule).not.toHaveAttribute('aria-invalid')
  })
})

describe('CALX355 — bloc ONDULEUR (rendement)', () => {
  it('rendement maximal, CEC et courbe (tension facultative) sont saisissables', async () => {
    renderEdit({ nom: 'Onduleur réseau Huawei 10kW' })
    await pret()
    fireEvent.change(screen.getByLabelText('Rendement maximal (%)'), { target: { value: '98.6' } })
    const bloc = screen.getByTestId('pf-courbe-ond_courbe_rendement')
    fireEvent.click(within(bloc).getByRole('button', { name: /Ajouter un point — Courbe de rendement/ }))
    fireEvent.change(within(bloc).getByLabelText('Charge (% de Pnom) — point 1'), { target: { value: '50' } })
    fireEvent.change(within(bloc).getByLabelText('Rendement (%) — point 1'), { target: { value: '98.2' } })
    fireEvent.click(screen.getByRole('button', { name: 'Mettre à jour' }))

    await waitFor(() => expect(createFicheTechnique).toHaveBeenCalled())
    const [payload] = createFicheTechnique.mock.calls[0]
    expect(payload.ond_rendement_max_pct).toBe(98.6)
    expect(payload.ond_rendement_cec_pct).toBeNull()
    expect(payload.ond_courbe_rendement).toEqual([{ charge_pct: 50, rendement_pct: 98.2 }])
  })
})

describe('CALX355 — bloc BATTERIE', () => {
  it('C-rate, chimie et plage de température ; une chimie non choisie part à \'\' et ne crée pas de fiche seule', async () => {
    renderEdit({ nom: 'Batterie lithium 5.12kWh' })
    await pret()
    expect(screen.getByLabelText('Température de fonctionnement mini (°C)')).toBeInTheDocument()
    expect(screen.getByLabelText('Température de fonctionnement maxi (°C)')).toBeInTheDocument()

    // Rien de saisi : aucune fiche créée (la chimie vide n'est pas une saisie).
    fireEvent.click(screen.getByRole('button', { name: 'Mettre à jour' }))
    await waitFor(() => expect(updateProduitApi).toHaveBeenCalled())
    expect(createFicheTechnique).not.toHaveBeenCalled()
  })

  it('la chimie choisie et le C-rate partent tels quels', async () => {
    renderEdit({ nom: 'Batterie lithium 5.12kWh' })
    await pret()
    fireEvent.change(screen.getByLabelText('C-rate de charge (C)'), { target: { value: '0.5' } })
    fireEvent.change(screen.getByLabelText('Chimie de cellule'), { target: { value: 'lfp' } })
    fireEvent.click(screen.getByRole('button', { name: 'Mettre à jour' }))

    await waitFor(() => expect(createFicheTechnique).toHaveBeenCalled())
    const [payload] = createFicheTechnique.mock.calls[0]
    expect(payload.type_fiche).toBe('batterie')
    expect(payload.bat_c_rate_charge).toBe(0.5)
    expect(payload.bat_chimie).toBe('lfp')
    expect(payload.bat_c_rate_decharge).toBeNull()
  })
})

describe('CALX355 — bloc OPTIMISEUR (sortie)', () => {
  it('un micro-onduleur non classé par le générateur ouvre le bloc sortie, écrit en type « optimiseur »', async () => {
    renderEdit({ nom: 'Micro-onduleur Hoymiles HMS-800' })
    await pret()
    expect(screen.queryByLabelText('Puissance AC (kW)')).not.toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Micro-onduleur — puissance AC nominale (kW)'), { target: { value: '0.8' } })
    fireEvent.click(screen.getByRole('button', { name: 'Mettre à jour' }))

    await waitFor(() => expect(createFicheTechnique).toHaveBeenCalled())
    const [payload] = createFicheTechnique.mock.calls[0]
    expect(payload.type_fiche).toBe('optimiseur')
    expect(payload.opt_ac_kw).toBe(0.8)
    expect(payload.opt_v_out_max).toBeNull()
  })
})
