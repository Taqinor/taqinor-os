// PVMRQ (fondateur 18/08/2026) — le générateur charge les réglages « Gammes &
// marques » (`ventesApi.getParametresGammes`, gamme Essentielle par défaut —
// aucune gamme n'est encore portée par un devis NEUF) et les applique à
// l'auto-remplissage : une marque épinglée sans AUCUN produit correspondant
// en stock affiche le bandeau dédié, EXACT même patron visuel que
// `errors.autofill` (« Aucun produit du stock ne correspond à… »), et ne
// retombe JAMAIS sur une autre marque déjà en stock.
//
// AVERTISSEMENT — vitest ne peut pas s'exécuter dans cet environnement (la
// jonction node_modules est vide) : ce fichier suit exactement le patron de
// DevisGeneratorTarif.test.jsx (rendu réel, mocks des couches api) mais n'a
// PAS été exécuté ici — seule la vérification de syntaxe (esbuild) l'a été.

import { describe, it, expect, vi, afterEach } from 'vitest'
import { screen, fireEvent, waitFor, renderHook, act } from '@testing-library/react'


vi.mock('../../api/crmApi', async () => (await import('../../test/mocksApiDevis.js')).crmApiMock())
vi.mock('../../api/stockApi', async () => (await import('../../test/mocksApiDevis.js')).stockApiDuplication())
vi.mock('../../api/parametresApi', async () => (await import('../../test/mocksApiDevis.js')).parametresApiMock())
vi.mock('../../api/ventesApi', async () => (await import('../../test/mocksApiDevis.js')).ventesApiMock({
    getDevisById: vi.fn(() => Promise.resolve({ data: {} })),
    getPrixApplicable: vi.fn(() => Promise.resolve({
      data: { source: 'standard' },
    })),
    // QJR577 (D-QJR5-9) — en résidentiel la composition (marques épinglées
    // comprises) est celle du dry-run SERVEUR : plus de repli local. Le mock
    // rend le verdict que le serveur rend pour ce réglage (Jinko épinglé,
    // introuvable) ; le test 2 le surcharge (réglage indisponible).
    composerDevis: vi.fn(() => Promise.resolve({
      data: {
        panel_watt: 710,
        marques_manquantes: [{ marque: 'Jinko', role: 'panneau' }],
        lignes: [
          { produit: 1, designation: 'Onduleur réseau Huawei 10kW Triphasé', quantite: 1, prix_unitaire_ht: 16666.67 },
          { produit: 7, designation: 'Installation', quantite: 1, prix_unitaire_ht: 4000 },
        ],
      },
    })),
    // PVMRQ — réglage « Gammes & marques » : Jinko épinglé pour les panneaux,
    // absent du catalogue de test ci-dessous (voir PRODUITS).
    getParametresGammes: vi.fn(() => Promise.resolve({
      data: {
        id: 1,
        deux_gammes: false,
        nom_essentielle: 'Essentielle',
        nom_premium: 'Premium',
        marques: { Essentielle: { panneau: 'Jinko' }, Premium: {} },
      },
    })),
}))

import crmApi from '../../api/crmApi'
import stockApi from '../../api/stockApi'
import ventesApi from '../../api/ventesApi'
import DevisGenerator from './DevisGenerator'
import { usePanneauParDefautDepart } from '../../features/ventes/quote/panneauDefautEcran'
import { PRODUITS_COMPOSITION as PRODUITS, bancCreation } from './devisGenerator.testHelpers.jsx'

// Catalogue solaire complet — SAUF un panneau Jinko : la seule marque de
// panneau en stock est Canadian Solar, jamais épinglée.

const { renderGenerator } = bancCreation({ DevisGenerator, crmApi, stockApi, produits: PRODUITS })


describe('PVMRQ — marque de panneau épinglée introuvable au stock', () => {
  // CIQ127 — l'écran ne charge plus le réglage « Gammes & marques » : plus
  // aucune composition locale ne l'appliquait (le dry-run serveur résidentiel
  // et le moteur C&I lisent eux-mêmes les marques épinglées de la société).
  it('l’écran ne charge plus le réglage : la préférence est appliquée par le serveur', async () => {
    renderGenerator()
    await screen.findByDisplayValue('Installation')
    expect(ventesApi.getParametresGammes).not.toHaveBeenCalled()
  })

  it('bandeau « Marque épinglée introuvable » à l\'auto-remplissage, JAMAIS un repli sur Canadian Solar', async () => {
    renderGenerator()
    // Rendu réel une fois le stock chargé — même patron que
    // DevisGeneratorTarif.test.jsx/DevisGeneratorLinesInput.test.jsx : on
    // attend un produit TOUJOURS pré-rempli par `defaultProductLines` au
    // montage (ici « Installation », seul candidat du rôle dans PRODUITS ;
    // « Onduleur réseau » y reste un simple PLACEHOLDER — jamais choisi au
    // montage, voir solar.js `defaultProductLines` — donc n'est PAS un anchor
    // valable avant le clic Auto-remplir).
    await screen.findByDisplayValue('Installation')

    fireEvent.change(screen.getByLabelText(/Nombre de panneaux/), { target: { value: '14' } })
    fireEvent.click(screen.getByRole('button', { name: /Auto-remplir depuis le stock/i }))

    expect(await screen.findByText(
      /Marque épinglée introuvable au stock : Jinko \(Panneaux\)/,
    )).toBeInTheDocument()
    expect(screen.getByText(/Paramètres → Gammes/)).toBeInTheDocument()
    // Jamais de repli silencieux sur le panneau Canadian Solar pourtant en stock.
    expect(screen.queryByDisplayValue('Panneau Canadien Solar 710W')).not.toBeInTheDocument()
    // La marque manquante n'ampute QUE le rôle panneau (seul rôle épinglé dans
    // ce réglage) : l'onduleur réseau, sans marque épinglée, reste
    // auto-rempli normalement avec le seul onduleur du stock.
    expect(await screen.findByDisplayValue(/Onduleur réseau Huawei/)).toBeInTheDocument()
  })

  it('sans réglage « Gammes & marques » accessible (403/erreur) : comportement historique, aucun bandeau', async () => {
    ventesApi.getParametresGammes.mockRejectedValueOnce({ response: { status: 403 } })
    ventesApi.composerDevis.mockResolvedValueOnce({
      data: {
        panel_watt: 710,
        marques_manquantes: [],
        lignes: [
          { produit: 1, designation: 'Onduleur réseau Huawei 10kW Triphasé', quantite: 1, prix_unitaire_ht: 16666.67 },
          { produit: 2, designation: 'Panneau Canadien Solar 710W', quantite: 14, prix_unitaire_ht: 1166.67 },
        ],
      },
    })
    renderGenerator()
    await screen.findByDisplayValue('Installation')

    fireEvent.change(screen.getByLabelText(/Nombre de panneaux/), { target: { value: '14' } })
    fireEvent.click(screen.getByRole('button', { name: /Auto-remplir depuis le stock/i }))

    // Le panneau Canadian Solar (seul en stock) est retenu normalement — pas
    // de préférence appliquée quand le réglage est indisponible.
    expect(await screen.findByDisplayValue('Panneau Canadien Solar 710W')).toBeInTheDocument()
    expect(screen.queryByText(/Marque épinglée introuvable/)).not.toBeInTheDocument()
  })
})

// D-ACAL-169 (fondateur 26/11/2026 : « always use 715w everywhere ») — le panneau par
// défaut de la société est la puissance de DÉPART d'un devis neuf ; ce que le vendeur tape
// gagne ; un devis rouvert ne le lit jamais ; sans défaut désigné rien ne change.
describe('D-ACAL-169 — panneau par défaut de la société', () => {
  const DEFAUT = {
    produit_id: 2, nom: 'Panneau Canadian Solar 715 Wc bifacial', pmax_wc: 715, source: 'designe', motif: null,
  }
  const AUCUN = {
    produit_id: null, nom: null, pmax_wc: null, source: 'aucun',
    motif: 'Aucun panneau par défaut n\'est désigné : les choix automatiques gardent leur règle d\'aujourd\'hui.',
  }
  const LIGNES = [
    { produit: 1, designation: 'Onduleur réseau Huawei 10kW Triphasé', quantite: 1, prix_unitaire_ht: 16666.67 },
    { produit: 2, designation: 'Panneau Canadien Solar 710W', quantite: 14, prix_unitaire_ht: 1166.67 },
  ]
  const lireDefaut = (resume) => { stockApi.getPanneauParDefaut = vi.fn(() => Promise.resolve({ data: resume })) }
  const composition = (panneauParDefaut, watt = 715) => ({
    data: { panel_watt: watt, marques_manquantes: [], lignes: LIGNES, panneau_par_defaut: panneauParDefaut },
  })
  const composer = async (nb = '14') => {
    fireEvent.change(screen.getByLabelText(/Nombre de panneaux/), { target: { value: nb } })
    fireEvent.click(screen.getByRole('button', { name: /Auto-remplir depuis le stock/i }))
    await screen.findByDisplayValue('Panneau Canadien Solar 710W')
    return ventesApi.composerDevis.mock.calls.at(-1)[0]
  }
  afterEach(() => { delete stockApi.getPanneauParDefaut })

  it('devis neuf + défaut désigné : départ à sa puissance, nom dit, la composition laisse le serveur choisir', async () => {
    lireDefaut(DEFAUT)
    ventesApi.composerDevis.mockResolvedValueOnce(composition(DEFAUT))
    renderGenerator()
    expect(await screen.findByDisplayValue('715')).toBeInTheDocument()
    expect(screen.getByTestId('gen-panneau-defaut')).toHaveTextContent('Panneau par défaut : Panneau Canadian Solar 715 Wc bifacial')
    const corps = await composer()
    // Ni wattage ni produit n'est dit au serveur : il applique sa règle (les deux de la même source).
    expect(corps).not.toHaveProperty('panel_watt')
    expect(corps.kwc).toBeCloseTo(10.01, 2)   // 14 × 715 W
    expect(stockApi.getPanneauParDefaut).toHaveBeenCalledTimes(1)
  })

  it('un wattage TAPÉ gagne : la phrase s’efface et la composition l’envoie', async () => {
    lireDefaut(DEFAUT)
    ventesApi.composerDevis.mockResolvedValueOnce(composition(DEFAUT, 600))
    renderGenerator()
    await screen.findByTestId('gen-panneau-defaut')
    fireEvent.change(screen.getByLabelText(/Puissance Panneau/), { target: { value: '600' } })
    expect(screen.queryByTestId('gen-panneau-defaut')).not.toBeInTheDocument()
    const corps = await composer()
    expect(corps.panel_watt).toBe(600)
  })

  it('le serveur refuse le défaut (`refuse`) : son motif est dit, rien d’autre ne change', async () => {
    lireDefaut(DEFAUT)
    const motif = 'Le panneau par défaut « Panneau Canadian Solar 715 Wc bifacial » n\'est pas retenu par la composition '
      + '(la marque épinglée des panneaux est « Jinko ») : la règle d\'aujourd\'hui s\'applique.'
    ventesApi.composerDevis.mockResolvedValueOnce(composition({
      produit_id: null, nom: null, pmax_wc: null, source: 'refuse', motif,
    }, 710))
    renderGenerator()
    await screen.findByTestId('gen-panneau-defaut')
    await composer()
    expect(await screen.findByText(/n'est pas retenu par la composition/)).toBeInTheDocument()
  })

  it('aucun défaut désigné : 710 comme avant, rien n’est dit, le wattage part comme avant', async () => {
    lireDefaut(AUCUN)
    ventesApi.composerDevis.mockResolvedValueOnce(composition(AUCUN, 710))
    renderGenerator()
    await screen.findByDisplayValue('Installation')
    await waitFor(() => expect(stockApi.getPanneauParDefaut).toHaveBeenCalled())
    expect(screen.getByLabelText(/Puissance Panneau/)).toHaveValue('710')
    expect(screen.queryByTestId('gen-panneau-defaut')).not.toBeInTheDocument()
    const corps = await composer()
    expect(corps.panel_watt).toBe(710)
  })

  it('lecture du défaut en échec : l’écran reste celui d’hier (710, wattage envoyé)', async () => {
    stockApi.getPanneauParDefaut = vi.fn(() => Promise.reject(new Error('réseau')))
    ventesApi.composerDevis.mockResolvedValueOnce(composition(AUCUN, 710))
    renderGenerator()
    await screen.findByDisplayValue('Installation')
    expect(screen.getByLabelText(/Puissance Panneau/)).toHaveValue('710')
    const corps = await composer()
    expect(corps.panel_watt).toBe(710)
  })

  it('un devis rouvert (editId) ne lit JAMAIS le défaut ; un devis neuf le lit une fois et le dit au reducer', async () => {
    lireDefaut(DEFAUT)
    const dispatchSizing = vi.fn()
    renderHook(() => usePanneauParDefautDepart({ editId: '7', dispatchSizing }))
    await act(async () => { await Promise.resolve() })
    expect(stockApi.getPanneauParDefaut).not.toHaveBeenCalled()
    expect(dispatchSizing).not.toHaveBeenCalled()

    renderHook(() => usePanneauParDefautDepart({ editId: null, dispatchSizing }))
    await waitFor(() => expect(dispatchSizing).toHaveBeenCalledWith({ type: 'PANNEAU_DEFAUT_LU', pmaxWc: 715 }))
    expect(stockApi.getPanneauParDefaut).toHaveBeenCalledTimes(1)
  })
})
