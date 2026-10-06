// CIQ125 — en industriel / commercial, UNE seule saisie de consommation : le
// profil déclaré (BlocEtudeReseau). Le corps de l'aperçu serveur porte ce qui
// est tapé, le résultat du moteur s'affiche tel quel (seule la réponse HTTP est
// simulée, À LA FORME du contrat `etude_ci_preview.json`), et sans
// consommation ni taille explicite l'enregistrement est refusé SOUS le champ.
// (Remplace QJR582 : la facture réelle résidentielle n'est plus montée en C&I.)
//
// Run : npx vitest run src/pages/ventes/DevisGeneratorConsoIC.test.jsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import authReducer from '../../features/auth/store/authSlice'
import ventesReducer from '../../features/ventes/store/ventesSlice'
import { exempleContrat, reponseContrat } from '../../test/fixtures/contractSamples'

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
    etudeCiPreview: vi.fn(),
  },
}))

import crmApi from '../../api/crmApi'
import stockApi from '../../api/stockApi'
import ventesApi from '../../api/ventesApi'
import DevisGenerator from './DevisGenerator'

const PANNEAU = { id: 101, nom: 'Panneau Canadien Solar 710W', prix_vente: 1100, tva: 10, is_archived: false }
const ONDULEUR = { id: 102, nom: 'Onduleur réseau 50kW Triphasé', prix_vente: 60000, tva: 20, is_archived: false }

function devisIndustriel(mode = 'industriel') {
  const contrat = exempleContrat('ventes', 'devis_modifiabilite', 'exemple_brouillon')
  return {
    data: {
      ...contrat, id: 55, lead: 8, client: 9, lead_nom: 'Usine Atlas',
      mode_installation: mode, taux_tva: '20.00', remise_globale: '0',
      etude_params: { scenario: 'Sans batterie' },
      lignes: [
        { id: 1, produit: PANNEAU.id, designation: PANNEAU.nom, quantite: '100',
          prix_unitaire: '1000.00', taux_tva: '10.00', ordre: 0, type_ligne: 'produit', optionnelle: false },
        { id: 2, produit: ONDULEUR.id, designation: ONDULEUR.nom, quantite: '1',
          prix_unitaire: '50000.00', taux_tva: '20.00', ordre: 1, type_ligne: 'produit', optionnelle: false },
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
  // Lead SANS facture : aucune autre source de consommation.
  crmApi.getLead.mockResolvedValue({ data: { id: 8, nom: 'Usine', prenom: 'Atlas' } })
  ventesApi.getDevisById.mockResolvedValue(devisIndustriel())
  ventesApi.patchDevis.mockResolvedValue({ data: {} })
  ventesApi.replaceLignesDevis.mockResolvedValue({ data: {} })
  ventesApi.patchEtudeParams.mockResolvedValue({ data: {} })
  ventesApi.etudeCiPreview.mockResolvedValue(reponseContrat('ventes', 'etude_ci_preview'))
})

const KWH = exempleContrat('ventes', 'etude_ci_preview').entrees_resolues.kwh_mensuels.valeur

function rendre() {
  return render(
    <Provider store={makeStore()}>
      <MemoryRouter initialEntries={['/ventes/devis/nouveau?edit=55']}>
        <Routes>
          <Route path="/ventes/devis/nouveau" element={<DevisGenerator />} />
          <Route path="*" element={<div>APRES</div>} />
        </Routes>
      </MemoryRouter>
    </Provider>,
  )
}

/** Réponse du contrat SANS consommation résolue (lead sans kWh). */
function reponseSansConso() {
  const r = reponseContrat('ventes', 'etude_ci_preview')
  r.data.entrees_resolues = {}
  return r
}

describe('CIQ125 — profil déclaré C&I et résultat serveur en direct', () => {
  it('saisir 12 kWh ⇒ le corps envoyé porte consommation.kwh_mensuels ; résultat affiché tel quel', async () => {
    const { container } = rendre()
    await waitFor(() => expect(container.querySelector('#gen-ci-kwh-0')).not.toBeNull())
    // le champ « kWh — pour l'étude » séparé n'existe plus
    expect(container.querySelector('#gen-conso')).toBeNull()
    expect(screen.queryByText(/pour l'étude/)).toBeNull()
    KWH.forEach((v, i) => {
      fireEvent.change(container.querySelector(`#gen-ci-kwh-${i}`), { target: { value: String(v) } })
    })
    await waitFor(() => {
      const appels = ventesApi.etudeCiPreview.mock.calls
      expect(appels.some(([corps]) => JSON.stringify(corps.consommation.kwh_mensuels) === JSON.stringify(KWH)))
        .toBe(true)
    }, { timeout: 3000 })
    const [corps] = ventesApi.etudeCiPreview.mock.calls.at(-1)
    expect(corps.mode).toBe('industriel')
    expect(corps.lead).toBe(8)
    const retenue = exempleContrat('ventes', 'etude_ci_preview').taille.retenue_kwc
    expect(await screen.findByTestId('ci-taille-retenue')).toHaveTextContent(String(retenue))
    expect(screen.getByTestId('ci-paliers')).toBeInTheDocument()
    expect(screen.getByTestId('ci-alertes')).toHaveTextContent('Vendeur seulement')
  })

  it.each(['industriel', 'commercial'])('%s sans consommation ni taille : enregistrement refusé sous le champ', async (mode) => {
    ventesApi.getDevisById.mockResolvedValue(devisIndustriel(mode))
    ventesApi.etudeCiPreview.mockResolvedValue(reponseSansConso())
    rendre()
    fireEvent.click(await screen.findByRole('button', { name: /Enregistrer les modifications/ }))
    expect(await screen.findByTestId('erreur-conso')).toHaveTextContent(/Renseignez la consommation du site/)
    expect(ventesApi.patchEtudeParams).not.toHaveBeenCalled()
  })

  it('enregistrer ⇒ les ENTRÉES v2 partent dans etude_params, jamais une dérivée du moteur', async () => {
    const { container } = rendre()
    await waitFor(() => expect(container.querySelector('#gen-ci-kwh-0')).not.toBeNull())
    KWH.forEach((v, i) => {
      fireEvent.change(container.querySelector(`#gen-ci-kwh-${i}`), { target: { value: String(v) } })
    })
    fireEvent.click(await screen.findByRole('button', { name: /Enregistrer les modifications/ }))
    await waitFor(() => expect(ventesApi.patchEtudeParams).toHaveBeenCalled())
    const [, bloc] = ventesApi.patchEtudeParams.mock.calls.at(-1)
    expect(bloc.mode).toBe('industriel')
    expect(bloc.consommation.kwh_mensuels).toEqual(KWH)
    expect(bloc).not.toHaveProperty('etude_ci')
    expect(bloc).not.toHaveProperty('production_figee')
    // CIQ126 — plus aucune clé de l'étude locale v1.
    for (const k of ['taux_autoconso', 'taux_couverture', 'payback', 'part_diurne_pct',
      'etude_kwc_base', 'injection_kwh_an', 'injection_dh_an', 'tension_raccordement', 'repartition_mt']) {
      expect(bloc).not.toHaveProperty(k)
    }
  })

  it('CIQ126 — Auto-remplir en industriel ⇒ un seul appel etude-ci/preview, lignes de la composition serveur', async () => {
    const compo = exempleContrat('ventes', 'etude_ci_preview').composition
    const ligneConnue = compo.lignes.find((l) => l.prix_connu && l.produit != null)
    const PRODUIT_MOTEUR = { id: ligneConnue.produit, nom: ligneConnue.designation, prix_vente: 50000, tva: 20, is_archived: false }
    stockApi.getProduits.mockResolvedValue({ data: [PANNEAU, ONDULEUR, PRODUIT_MOTEUR] })
    const { container } = rendre()
    await waitFor(() => expect(container.querySelector('#gen-ci-kwh-0')).not.toBeNull())
    KWH.forEach((v, i) => {
      fireEvent.change(container.querySelector(`#gen-ci-kwh-${i}`), { target: { value: String(v) } })
    })
    // l'aperçu en direct a répondu
    await screen.findByTestId('ci-taille-retenue', {}, { timeout: 3000 })
    const avant = ventesApi.etudeCiPreview.mock.calls.length
    fireEvent.click(screen.getByTestId('btn-auto-remplir'))
    expect(await screen.findByDisplayValue(ligneConnue.designation)).toBeInTheDocument()
    expect(ventesApi.etudeCiPreview.mock.calls.length - avant).toBe(1)
    // un article « prix à renseigner » est nommé, jamais chiffré
    const aRenseigner = compo.lignes.find((l) => l.prix_connu === false)
    expect(await screen.findByDisplayValue(`${aRenseigner.designation} — prix à renseigner`)).toBeInTheDocument()
  })
})
