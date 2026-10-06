// QJR624 (D-QJR5-10) — l'échéancier (acompte / matériel / solde) est éditable
// dans l'Édition complète : relu au chargement `?edit=`, modifié, et envoyé
// dans `entete.echeancier` de replace-lines (contrat QJR504, exemple COMMITTÉ
// `devis_replace_lines_entete.json` — PACT10). Un devis qui suit l'échéancier
// de la société n'en reçoit pas un figé en silence.
//
// Run : npx vitest run src/pages/ventes/DevisGeneratorEcheancier.test.jsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import authReducer from '../../features/auth/store/authSlice'
import ventesReducer from '../../features/ventes/store/ventesSlice'
import { estimerMois } from '../../features/ventes/solar'
import { documentContrat, exempleContrat } from '../../test/fixtures/contractSamples'
import {
  echeancierAvecAcompte, echeancierVersSaisie, saisieVersEcheancier, saisieParDefaut,
} from '../../features/ventes/echeancierEdition'

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
import parametresApi from '../../api/parametresApi'
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
const LEAD = {
  id: 77, nom: 'Khalid', prenom: 'SansStatut', societe: '',
  facture_hiver: '3000', ete_differente: false, facture_ete: null,
  ville: 'Mohammedia',
}

function devisRouvert(variante, echeancier) {
  const contrat = exempleContrat('ventes', 'devis_modifiabilite', variante)
  return {
    data: {
      ...contrat, echeancier, lead: LEAD.id, client: 9, date_envoi: '2026-09-28T10:00:00Z',
      mode_installation: 'residentiel', taux_tva: '20.00', remise_globale: '0',
      etude_params: {
        scenario: 'Sans batterie',
        factures_mensuelles_reelles: estimerMois(3000, 3000),
      },
      lignes: [
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

function renderEdition(id) {
  return render(
    <Provider store={makeStore()}>
      <MemoryRouter initialEntries={[`/ventes/devis/nouveau?edit=${id}`]}>
        <Routes>
          <Route path="/ventes/devis/nouveau" element={<DevisGenerator />} />
          <Route path="*" element={<div>APRES-ENREGISTREMENT</div>} />
        </Routes>
      </MemoryRouter>
    </Provider>,
  )
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

const enMode = (r, mode) => ({ data: { ...r.data, mode_installation: mode } })

const EFFECTIFS = {
  residentiel: [
    { jalon: 'acompte', libelle: 'Acompte', pct: 30 },
    { jalon: 'materiel', libelle: 'Livraison du matériel', pct: 60 },
    { jalon: 'solde', libelle: 'Solde', pct: 10 },
  ],
}

const ECHEANCIER = documentContrat('ventes', 'devis_replace_lines_entete')
  .corps.entete.echeancier

describe('QJR624 — échéancier : helpers', () => {
  it('aller-retour serveur → saisie → serveur sans perte', () => {
    const saisie = echeancierVersSaisie(ECHEANCIER)
    expect(saisie.map(t => t.unite)).toEqual(['pct', 'pct'])
    expect(saisieVersEcheancier(saisie).map(t => t.pct_or_montant))
      .toEqual(ECHEANCIER.map(t => t.pct_or_montant))
    expect(echeancierVersSaisie([])).toBeNull()
    expect(saisieVersEcheancier(null)).toEqual([])
  })

  it('acompte personnalisé : première tranche en MAD, le matériel absorbe l\'écart', () => {
    const e = echeancierAvecAcompte(null, '20000', 100000, 'residentiel', EFFECTIFS)
    expect(e[0]).toMatchObject({ type: 'acompte', unite: 'montant', pct_or_montant: 20000 })
    expect(e[1]).toMatchObject({ type: 'materiel', unite: 'pct', pct_or_montant: 70 })
    expect(e[2]).toMatchObject({ type: 'solde', unite: 'pct', pct_or_montant: 10 })
  })
})

// AGR220 — date de solde « après récolte » (forme du contrat partagé).
const ECHEANCIER_AGRICOLE = documentContrat('ventes', 'devis_replace_lines_entete')
  .corps_agricole.entete.echeancier

describe('AGR220 — date facultative par tranche', () => {
  it('relue puis renvoyée : enregistrer sans toucher = échéancier serveur identique', () => {
    const rendu = saisieVersEcheancier(echeancierVersSaisie(ECHEANCIER_AGRICOLE))
    expect(rendu.map(t => t.date_prevue ?? null))
      .toEqual(ECHEANCIER_AGRICOLE.map(t => t.date_prevue ?? null))
    expect(rendu[2].date_prevue).toBe('2027-03-31')
    // Date absente : la clé n'est pas envoyée (le serveur l'omet quand null).
    expect(rendu[0]).not.toHaveProperty('date_prevue')
  })

  it('mode agricole : la tranche de solde propose « Solde après récolte »', () => {
    expect(saisieParDefaut('agricole')[2].libelle).toBe('Solde après récolte')
    expect(saisieParDefaut('residentiel', EFFECTIFS)[2].libelle).toBe('Solde')
  })

  it('date saisie dans la carte ⇒ envoyée dans entete.echeancier', async () => {
    const rouvert = devisRouvert('exemple_envoye', ECHEANCIER_AGRICOLE)
    ventesApi.getDevisById.mockResolvedValue(rouvert)
    renderEdition(rouvert.data.id)
    await waitFor(() => expect(crmApi.getLead).toHaveBeenCalledWith(77))
    const carte = await screen.findByTestId('carte-echeancier')
    expect(carte.querySelector('#gen-echeance-date-2').value).toBe('2027-03-31')
    fireEvent.change(carte.querySelector('#gen-echeance-date-2'), { target: { value: '2027-04-15' } })
    await userEvent.click(await screen.findByRole('button', { name: /Enregistrer les modifications/ }))
    await waitFor(() => expect(ventesApi.replaceLignesDevis).toHaveBeenCalled())
    const [, , { entete }] = ventesApi.replaceLignesDevis.mock.calls.at(-1)
    expect(entete.echeancier[2].date_prevue).toBe('2027-04-15')
    expect(entete.echeancier[0]).not.toHaveProperty('date_prevue')
  })
})

describe('QJR624 — l\'échéancier s\'édite dans l\'Édition complète', () => {
  it('chargé depuis le devis, modifié, envoyé dans entete', async () => {
    const rouvert = devisRouvert('exemple_envoye', ECHEANCIER)
    ventesApi.getDevisById.mockResolvedValue(rouvert)
    renderEdition(rouvert.data.id)
    await waitFor(() => expect(crmApi.getLead).toHaveBeenCalledWith(77))
    const carte = await screen.findByTestId('carte-echeancier')
    const acompte = carte.querySelector('#gen-echeance-0')
    expect(acompte.value).toBe(String(ECHEANCIER[0].pct_or_montant))
    fireEvent.change(acompte, { target: { value: '45' } })
    fireEvent.change(carte.querySelector('#gen-echeance-1'), { target: { value: '55' } })
    await userEvent.click(await screen.findByRole('button', { name: /Enregistrer les modifications/ }))
    await waitFor(() => expect(ventesApi.replaceLignesDevis).toHaveBeenCalled())
    const [, , { entete }] = ventesApi.replaceLignesDevis.mock.calls.at(-1)
    expect(entete.echeancier.map(t => t.pct_or_montant)).toEqual([45, 55])
    expect(entete.echeancier[0]).toMatchObject({ type: 'acompte', unite: 'pct' })
  })

  it('devis qui suit la société : rien n\'est envoyé tant qu\'on ne personnalise pas', async () => {
    const rouvert = devisRouvert('exemple_brouillon', [])
    ventesApi.getDevisById.mockResolvedValue(rouvert)
    renderEdition(rouvert.data.id)
    await waitFor(() => expect(crmApi.getLead).toHaveBeenCalledWith(77))
    await screen.findByTestId('carte-echeancier')
    await userEvent.click(await screen.findByRole('button', { name: /Enregistrer les modifications/ }))
    await waitFor(() => expect(ventesApi.replaceLignesDevis).toHaveBeenCalled())
    const [, , { entete }] = ventesApi.replaceLignesDevis.mock.calls.at(-1)
    expect(entete).not.toHaveProperty('echeancier')
  })

  it('personnaliser puis enregistrer envoie l\'échéancier par défaut du mode', async () => {
    parametresApi.getProfile.mockResolvedValue({ data: { payment_terms_effectifs: EFFECTIFS } })
    const rouvert = devisRouvert('exemple_brouillon', [])
    ventesApi.getDevisById.mockResolvedValue(rouvert)
    renderEdition(rouvert.data.id)
    await waitFor(() => expect(crmApi.getLead).toHaveBeenCalledWith(77))
    await userEvent.click(await screen.findByRole('button', { name: /Personnaliser l'échéancier/ }))
    await userEvent.click(await screen.findByRole('button', { name: /Enregistrer les modifications/ }))
    await waitFor(() => expect(ventesApi.replaceLignesDevis).toHaveBeenCalled())
    const [, , { entete }] = ventesApi.replaceLignesDevis.mock.calls.at(-1)
    expect(entete.echeancier.map(t => t.pct_or_montant)).toEqual([30, 60, 10])
  })

  // CIQ225 — le défaut vient de `payment_terms_effectifs`, pas d'une constante JS.
  it('devis industriel : « Personnaliser » propose les 4 jalons du profil', async () => {
    parametresApi.getProfile.mockResolvedValue({ data: { payment_terms_effectifs: {
      ...EFFECTIFS,
      industriel: [
        { jalon: 'commande', libelle: 'Commande', pct: 25 },
        { jalon: 'livraison_materiel', libelle: 'Livraison du matériel', pct: 45 },
        { jalon: 'mise_en_service', libelle: 'Mise en service', pct: 20 },
        { jalon: 'reception_definitive', libelle: 'Réception définitive', pct: 10 },
      ],
    } } })
    const rouvert = enMode(devisRouvert('exemple_brouillon', []), 'industriel')
    ventesApi.getDevisById.mockResolvedValue(rouvert)
    renderEdition(rouvert.data.id)
    await waitFor(() => expect(parametresApi.getProfile).toHaveBeenCalled())
    await userEvent.click(await screen.findByRole('button', { name: /Personnaliser l'échéancier/ }))
    const carte = await screen.findByTestId('carte-echeancier')
    expect([0, 1, 2, 3].map(i => carte.querySelector(`#gen-echeance-${i}`).value))
      .toEqual(['25', '45', '20', '10'])
    fireEvent.change(carte.querySelector('#gen-echeance-delai-3'), { target: { value: '30' } })
    fireEvent.change(carte.querySelector('#gen-echeance-semaines-1'), { target: { value: '6.5' } })
    await userEvent.click(await screen.findByRole('button', { name: /Enregistrer les modifications/ }))
    await waitFor(() => expect(ventesApi.replaceLignesDevis).toHaveBeenCalled())
    const [, , { entete }] = ventesApi.replaceLignesDevis.mock.calls.at(-1)
    expect(entete.echeancier.map(t => t.jalon)).toEqual(
      ['commande', 'livraison_materiel', 'mise_en_service', 'reception_definitive'])
    expect(entete.echeancier[3].delai_reglement_jours).toBe(30)
    expect(entete.echeancier[1].semaines_indicatives).toBe(6.5)
    expect(entete.echeancier[0]).not.toHaveProperty('delai_reglement_jours')
  })

  it('4 jalons enregistrés → rouvrir → enregistrer sans toucher = identique', async () => {
    const serveur = [
      { libelle: 'Commande', type: 'commande', jalon: 'commande', unite: 'pct', pct_or_montant: 30 },
      { libelle: 'Livraison du matériel', type: 'livraison_materiel', jalon: 'livraison_materiel', unite: 'pct', pct_or_montant: 40, semaines_indicatives: 6 },
      { libelle: 'Mise en service', type: 'mise_en_service', jalon: 'mise_en_service', unite: 'pct', pct_or_montant: 20 },
      { libelle: 'Réception définitive', type: 'reception_definitive', jalon: 'reception_definitive', unite: 'pct', pct_or_montant: 10, delai_reglement_jours: 30 },
    ]
    expect(saisieVersEcheancier(echeancierVersSaisie(serveur))).toEqual(serveur)
    const rouvert = enMode(devisRouvert('exemple_envoye', serveur), 'industriel')
    ventesApi.getDevisById.mockResolvedValue(rouvert)
    renderEdition(rouvert.data.id)
    await waitFor(() => expect(crmApi.getLead).toHaveBeenCalledWith(77))
    await screen.findByTestId('carte-echeancier')
    await userEvent.click(await screen.findByRole('button', { name: /Enregistrer les modifications/ }))
    await waitFor(() => expect(ventesApi.replaceLignesDevis).toHaveBeenCalled())
    const [, , { entete }] = ventesApi.replaceLignesDevis.mock.calls.at(-1)
    expect(entete.echeancier).toEqual(serveur)
  })

  it('somme ≠ 100 ⇒ message sous la liste', async () => {
    const rouvert = devisRouvert('exemple_envoye', ECHEANCIER)
    ventesApi.getDevisById.mockResolvedValue(rouvert)
    renderEdition(rouvert.data.id)
    await waitFor(() => expect(crmApi.getLead).toHaveBeenCalledWith(77))
    const carte = await screen.findByTestId('carte-echeancier')
    fireEvent.change(carte.querySelector('#gen-echeance-0'), { target: { value: '10' } })
    expect(await screen.findByTestId('echeancier-somme')).toHaveTextContent('100 %')
  })
})
