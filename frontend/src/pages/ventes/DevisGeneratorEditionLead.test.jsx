// Réouverture d'un devis (`?edit=`) — l'écran RÉEL est rendu et ce que
// l'enregistrement envoie est lu sur les API mockées : aucune lecture de
// source (QJR239 / `scripts/check_tests_source_regex.py`).
//
//   · ERR-QAH-VENTES-EDITION-PERD-LEAD — le lead du devis est relu par son id
//     (il manquait de la première page de `leads`), sa relecture est isolée
//     (une panne ne casse pas le chargement), et les 12 factures RÉELLES du
//     devis remplacent la grille d'exemple (500/450/400…).
//   · ERR-QAH-FIG-EDITION-PU-TTC-ARRONDI — le mappeur `?edit=` reconvertit
//     chaque prix HT persisté au CENTIME : ré-enregistrer rend le même HT.
//   · ERR-QAC-FACTURES-ECRAN-INVRAISEMBLABLES — une facture sous les lignes
//     fixes du compteur bloque l'enregistrement ; un écart avec la facture
//     d'hiver du lead se fait confirmer par un second clic.
//
// Run : npx vitest run src/pages/ventes/DevisGeneratorEditionLead.test.jsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import authReducer from '../../features/auth/store/authSlice'
import ventesReducer from '../../features/ventes/store/ventesSlice'
import { estimerMois, DEFAULT_MONTHLY_BILLS } from '../../features/ventes/solar'

vi.mock('../../api/crmApi', () => ({
  default: {
    getClients: vi.fn(() => Promise.resolve({ data: [] })),
    getLeads: vi.fn(() => Promise.resolve({ data: [] })),
    getLead: vi.fn(),
  },
}))
vi.mock('../../api/stockApi', () => ({
  default: { getProduits: vi.fn(() => Promise.resolve({ data: [] })) },
}))
vi.mock('../../api/parametresApi', () => ({
  default: { getProfile: vi.fn(() => Promise.resolve({ data: {} })) },
}))
vi.mock('../../api/ventesApi', () => ({
  default: {
    getDevisById: vi.fn(() => Promise.resolve({ data: {} })),
    getParametresGammes: vi.fn(() => Promise.resolve({ data: {} })),
    getPrefillSite: vi.fn(() => Promise.resolve({ data: {} })),
    getOffresTaillesDevis: vi.fn(() => Promise.resolve({ data: { editable: false } })),
    lireOverrides: vi.fn(() => Promise.resolve({ data: {} })),
    getPrixApplicable: vi.fn(),
    patchDevis: vi.fn(),
    replaceLignesDevis: vi.fn(),
    createDevisAtomic: vi.fn(),
    patchEtudeParams: vi.fn(),
  },
}))

import crmApi from '../../api/crmApi'
import stockApi from '../../api/stockApi'
import ventesApi from '../../api/ventesApi'
import DevisGenerator from './DevisGenerator'

const PANNEAU = {
  id: 101, nom: 'Panneau Canadien Solar 715W', prix_vente: 1200, tva: 10,
  is_archived: false, prix_achat: 800,
}
const ONDULEUR = {
  id: 102, nom: 'Onduleur réseau 5kW Monophasé', prix_vente: 9000, tva: 20,
  is_archived: false, prix_achat: 6000,
}

// Lead ABSENT de la première page de `leads` (getLeads rend []).
const LEAD = {
  id: 77, nom: 'Khalid', prenom: 'Réouvert', societe: '',
  facture_hiver: '3000', ete_differente: false, facture_ete: null,
  ville: 'Mohammedia',
}

function devisRouvert({ lead = LEAD.id, etudeParams = {}, lignes } = {}) {
  return {
    data: {
      id: 336, reference: 'DEV-202609-0200', statut: 'brouillon', modifiable: true, raison_non_modifiable: '', revision_possible: false, is_active: true, lead, client: 9,
      mode_installation: 'residentiel', taux_tva: '20.00', remise_globale: '0',
      etude_params: { scenario: 'Sans batterie', ...etudeParams },
      lignes: lignes || [
        { id: 1, produit: PANNEAU.id, designation: PANNEAU.nom, quantite: '8',
          prix_unitaire: '1200.00', taux_tva: '10.00', ordre: 0,
          type_ligne: 'produit', optionnelle: false },
        { id: 2, produit: ONDULEUR.id, designation: ONDULEUR.nom, quantite: '1',
          prix_unitaire: '9000.00', taux_tva: '20.00', ordre: 1,
          type_ligne: 'produit', optionnelle: false },
      ],
    },
  }
}

function makeStore() {
  return configureStore({
    reducer: { auth: authReducer, ventes: ventesReducer },
    preloadedState: {
      auth: {
        user: { id: 1 }, role: 'normal', role_nom: 'Commercial', permissions: [],
        isAuthenticated: true, loading: false,
      },
    },
  })
}

function renderEdition() {
  return render(
    <Provider store={makeStore()}>
      <MemoryRouter initialEntries={['/ventes/devis/nouveau?edit=336']}>
        <Routes>
          <Route path="/ventes/devis/nouveau" element={<DevisGenerator />} />
          <Route path="*" element={<div>APRES-ENREGISTREMENT</div>} />
        </Routes>
      </MemoryRouter>
    </Provider>,
  )
}

async function cliquerEnregistrer() {
  const bouton = await screen.findByRole('button', { name: /Enregistrer les modifications/ })
  await userEvent.click(bouton)
}

async function enregistrerEtLireEtude() {
  await cliquerEnregistrer()
  await waitFor(() => expect(ventesApi.patchEtudeParams).toHaveBeenCalled())
  return ventesApi.patchEtudeParams.mock.calls.at(-1)[1]
}

beforeEach(() => {
  vi.clearAllMocks()
  try { window.localStorage.clear() } catch { /* stockage indisponible */ }
  if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {}
  if (!window.matchMedia) {
    window.matchMedia = vi.fn().mockImplementation((q) => ({
      matches: false, media: q, onchange: null,
      addListener: vi.fn(), removeListener: vi.fn(),
      addEventListener: vi.fn(), removeEventListener: vi.fn(), dispatchEvent: vi.fn(),
    }))
  }
  if (!globalThis.ResizeObserver) {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
  }
  stockApi.getProduits.mockResolvedValue({ data: [PANNEAU, ONDULEUR] })
  crmApi.getLead.mockResolvedValue({ data: LEAD })
  ventesApi.patchDevis.mockResolvedValue({ data: {} })
  ventesApi.replaceLignesDevis.mockResolvedValue({ data: {} })
  ventesApi.patchEtudeParams.mockResolvedValue({ data: {} })
})

describe('ERR-QAH-VENTES-EDITION-PERD-LEAD — le lead et les factures du devis rouvert', () => {
  it('relit le lead par son id et renvoie les 12 factures RÉELLES du devis, jamais la grille d\'exemple', async () => {
    const factures = estimerMois(3000, 3000)
    ventesApi.getDevisById.mockResolvedValue(devisRouvert({
      etudeParams: { factures_mensuelles_reelles: factures },
    }))
    renderEdition()
    await waitFor(() => expect(crmApi.getLead).toHaveBeenCalledWith(77))
    // Le lead relu (absent de la page `leads`) est le lead SÉLECTIONNÉ.
    expect((await screen.findAllByText(/Khalid Réouvert/)).length).toBeGreaterThan(0)
    const cles = await enregistrerEtLireEtude()
    expect(cles.factures_mensuelles_reelles).toEqual(factures)
    expect(cles.factures_mensuelles_reelles).not.toEqual(DEFAULT_MONTHLY_BILLS)
  })

  it('une panne de la relecture du lead ne casse pas le chargement du devis', async () => {
    crmApi.getLead.mockRejectedValue(new Error('réseau'))
    ventesApi.getDevisById.mockResolvedValue(devisRouvert({
      etudeParams: { factures_mensuelles_reelles: estimerMois(3000, 3000) },
    }))
    renderEdition()
    await waitFor(() => expect(crmApi.getLead).toHaveBeenCalledWith(77))
    const cles = await enregistrerEtLireEtude()
    expect(cles.factures_mensuelles_reelles).toEqual(estimerMois(3000, 3000))
  })
})

describe('ERR-QAH-FIG-EDITION-PU-TTC-ARRONDI — prix persistés gardés au centime', () => {
  it('ré-enregistrer un devis rouvert renvoie EXACTEMENT les prix HT d\'origine', async () => {
    ventesApi.getDevisById.mockResolvedValue(devisRouvert({
      etudeParams: { factures_mensuelles_reelles: estimerMois(3000, 3000) },
      lignes: [
        // TTC non entiers : 343,739 et 1 249,50 — l'arrondi au dirham les
        // déplaçait (343 / 1 250) puis re-dérivait un autre HT.
        { id: 1, produit: PANNEAU.id, designation: PANNEAU.nom, quantite: '14',
          prix_unitaire: '312.49', taux_tva: '10.00', ordre: 0,
          type_ligne: 'produit', optionnelle: false },
        { id: 2, produit: ONDULEUR.id, designation: ONDULEUR.nom, quantite: '1',
          prix_unitaire: '1041.25', taux_tva: '20.00', ordre: 1,
          type_ligne: 'produit', optionnelle: false },
      ],
    }))
    renderEdition()
    await cliquerEnregistrer()
    await waitFor(() => expect(ventesApi.replaceLignesDevis).toHaveBeenCalled())
    const lignes = ventesApi.replaceLignesDevis.mock.calls.at(-1)[1]
    const prix = Object.fromEntries(
      lignes.map(l => [String(l.designation), Number(l.prix_unitaire)]))
    expect(prix[PANNEAU.nom]).toBe(312.49)
    expect(prix[ONDULEUR.nom]).toBe(1041.25)
  })
})

describe('ERR-QAC-FACTURES-ECRAN-INVRAISEMBLABLES — contrôle des factures à l\'enregistrement', () => {
  it('une facture sous les lignes fixes du compteur BLOQUE l\'enregistrement (DEV-202609-0108)', async () => {
    ventesApi.getDevisById.mockResolvedValue(devisRouvert({
      etudeParams: { factures_mensuelles_reelles: estimerMois(1, 1600) },
    }))
    renderEdition()
    await cliquerEnregistrer()
    const erreur = await screen.findByTestId('erreur-enregistrement')
    expect(erreur).toHaveTextContent(/inférieure\(s\) aux lignes fixes/)
    expect(erreur).toHaveTextContent(/mois 1, 12/)
    expect(ventesApi.patchDevis).not.toHaveBeenCalled()
    expect(ventesApi.patchEtudeParams).not.toHaveBeenCalled()
  })

  it("un écart avec la facture d'hiver du lead se CONFIRME : premier clic bloqué, second enregistre", async () => {
    ventesApi.getDevisById.mockResolvedValue(devisRouvert({
      etudeParams: { factures_mensuelles_reelles: estimerMois(1600, 1600) },
    }))
    renderEdition()
    await waitFor(() => expect(crmApi.getLead).toHaveBeenCalledWith(77))
    await screen.findAllByText(/Khalid Réouvert/)
    await cliquerEnregistrer()
    const erreur = await screen.findByTestId('erreur-enregistrement')
    expect(erreur).toHaveTextContent(/s'écarte de celle du lead \(3000 MAD\)/)
    expect(ventesApi.patchEtudeParams).not.toHaveBeenCalled()
    const cles = await enregistrerEtLireEtude()
    expect(cles.factures_mensuelles_reelles).toEqual(estimerMois(1600, 1600))
  })
})

describe('ERR-QAC-KWH-SAISI-INCOHERENT-FACTURES — kWh déclaré contredit par les factures', () => {
  it('46 kWh/mois face à 15 000 MAD/mois BLOQUE l\'enregistrement (DEV-202609-0082)', async () => {
    crmApi.getLead.mockResolvedValue({
      data: { ...LEAD, facture_hiver: '15000', conso_mensuelle_kwh: '46' },
    })
    ventesApi.getDevisById.mockResolvedValue(devisRouvert({
      etudeParams: { factures_mensuelles_reelles: estimerMois(15000, 15000) },
    }))
    renderEdition()
    await waitFor(() => expect(crmApi.getLead).toHaveBeenCalledWith(77))
    await screen.findAllByText(/Khalid Réouvert/)
    await cliquerEnregistrer()
    const erreur = await screen.findByTestId('erreur-enregistrement')
    expect(erreur).toHaveTextContent(
      'kWh déclarés incohérents avec les factures — corriger la fiche du lead')
    expect(ventesApi.replaceLignesDevis).not.toHaveBeenCalled()
    expect(ventesApi.patchEtudeParams).not.toHaveBeenCalled()
  })

  it('un kWh concordant (650 kWh/mois ≈ 1 200 MAD) enregistre normalement', async () => {
    crmApi.getLead.mockResolvedValue({
      data: { ...LEAD, facture_hiver: '1200', conso_mensuelle_kwh: '650' },
    })
    ventesApi.getDevisById.mockResolvedValue(devisRouvert({
      etudeParams: { factures_mensuelles_reelles: estimerMois(1200, 1200) },
    }))
    renderEdition()
    await waitFor(() => expect(crmApi.getLead).toHaveBeenCalledWith(77))
    await screen.findAllByText(/Khalid Réouvert/)
    await enregistrerEtLireEtude()
    expect(ventesApi.replaceLignesDevis).toHaveBeenCalled()
  })
})
