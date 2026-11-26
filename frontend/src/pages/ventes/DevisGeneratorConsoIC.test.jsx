// CIQ125 — en industriel / commercial, UNE seule saisie de consommation : le
// profil déclaré (BlocEtudeReseau). Le corps de l'aperçu serveur porte ce qui
// est tapé, le résultat du moteur s'affiche tel quel (seule la réponse HTTP est
// simulée, À LA FORME du contrat `etude_ci_preview.json`), et sans
// consommation ni taille explicite l'enregistrement est refusé SOUS le champ.
// (Remplace QJR582 : la facture réelle résidentielle n'est plus montée en C&I.)
//
// Run : npx vitest run src/pages/ventes/DevisGeneratorConsoIC.test.jsx
import { describe, it, expect, vi } from 'vitest'
import { act, screen, waitFor, fireEvent } from '@testing-library/react'

import { exempleContrat, reponseContrat } from '../../test/fixtures/contractSamples'

vi.mock('../../api/crmApi', async () => (await import('../../test/mocksApiDevis.js')).crmApiAvecLead())
vi.mock('../../api/stockApi', async () => (await import('../../test/mocksApiDevis.js')).stockApiMock())
vi.mock('../../api/parametresApi', async () => (await import('../../test/mocksApiDevis.js')).parametresApiMock())
vi.mock('../../api/ventesApi', async () => (await import('../../test/mocksApiDevis.js')).ventesApiEdition({
    etudeCiPreview: vi.fn(), economieCiPreview: vi.fn(),
}))

import crmApi from '../../api/crmApi'
import stockApi from '../../api/stockApi'
import ventesApi from '../../api/ventesApi'
import DevisGenerator from './DevisGenerator'
import { declarerBeforeEachDevis, makeDevisStore, mockEcrituresDevisOk, renderEditionPage } from './devisGenerator.testHelpers.jsx'

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

const makeStore = () => makeDevisStore('normal', 'Commercial')

declarerBeforeEachDevis({
  stockApi, crmApi, ventesApi, produits: [PANNEAU, ONDULEUR], localStorage: true,
  extra: () => {
    // Lead SANS facture : aucune autre source de consommation.
    crmApi.getLead.mockResolvedValue({ data: { id: 8, nom: 'Usine', prenom: 'Atlas' } })
    ventesApi.getDevisById.mockResolvedValue(devisIndustriel())
    mockEcrituresDevisOk(ventesApi)
    ventesApi.etudeCiPreview.mockResolvedValue(reponseContrat('ventes', 'etude_ci_preview'))
    ventesApi.economieCiPreview.mockResolvedValue(reponseContrat('ventes', 'economie_ci'))
  },
})

const KWH = exempleContrat('ventes', 'etude_ci_preview').entrees_resolues.kwh_mensuels.valeur

function rendre() {
  return renderEditionPage(DevisGenerator, makeStore(), 55)
}

/** Réponse du contrat SANS consommation résolue (lead sans kWh). */
function reponseSansConso() {
  const r = reponseContrat('ventes', 'etude_ci_preview')
  r.data.entrees_resolues = {}
  r.data.feuille_consommation_retenue = null // ADEV120 — aucune feuille retenue
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

  it('ADEV91 — le kWh MENSUEL du lead résolu par le serveur (kwh_mensuel_declare) vaut consommation connue', async () => {
    // Lead Meta : un seul kWh mensuel, aucun profil saisi — l'aperçu a calculé
    // (30,53 kWc en direct) : « Créer / Enregistrer » ne refuse plus.
    ventesApi.getDevisById.mockResolvedValue(devisIndustriel('commercial'))
    const r = reponseSansConso()
    r.data.entrees_resolues = { kwh_mensuel_declare: { valeur: 6000, provenance: { origine: 'lead', detail: 'client' } } }
    r.data.feuille_consommation_retenue = 'kwh_mensuel_declare' // ce que le serveur sert alors (AMOT104)
    ventesApi.etudeCiPreview.mockResolvedValue(r)
    rendre()
    // L'aperçu serveur doit être LU avant d'enregistrer (c'est lui qui porte
    // la consommation résolue) : la taille retenue affichée en est la preuve.
    const retenue = exempleContrat('ventes', 'etude_ci_preview').taille.retenue_kwc
    expect(await screen.findByTestId('ci-taille-retenue', {}, { timeout: 5000 })).toHaveTextContent(String(retenue))
    fireEvent.click(await screen.findByRole('button', { name: /Enregistrer les modifications/ }))
    await waitFor(() => expect(ventesApi.patchEtudeParams).toHaveBeenCalled(), { timeout: 5000 })
    expect(screen.queryByTestId('erreur-conso')).toBeNull()
  })

  it("ADEV120 — facture d'hiver seule résolue vaut consommation connue", async () => {
    // C-ADEV-VER4-031 — l'aperçu a chiffré sur `facture_hiver_mad` (feuille
    // retenue servie, AMOT104) : l'écran ne refuse plus « Enregistrer ».
    ventesApi.getDevisById.mockResolvedValue(devisIndustriel('commercial'))
    const r = reponseSansConso()
    r.data.entrees_resolues = { facture_hiver_mad: { valeur: 3500, provenance: { origine: 'lead', detail: 'client' } } }
    r.data.feuille_consommation_retenue = 'facture_hiver_mad'
    ventesApi.etudeCiPreview.mockResolvedValue(r)
    rendre()
    const retenue = exempleContrat('ventes', 'etude_ci_preview').taille.retenue_kwc
    expect(await screen.findByTestId('ci-taille-retenue', {}, { timeout: 5000 })).toHaveTextContent(String(retenue))
    fireEvent.click(await screen.findByRole('button', { name: /Enregistrer les modifications/ }))
    await waitFor(() => expect(ventesApi.patchEtudeParams).toHaveBeenCalled(), { timeout: 5000 })
    expect(screen.queryByTestId('erreur-conso')).toBeNull()
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

// T4-X6-007 / 008 / 010 / 011 — l'édition complète d'un devis C&I : l'aperçu décrit les
// LIGNES du devis (une valeur par option), le moteur ne fait que CONSEILLER sa taille ; un
// seul retour pour l'offre réseau ; « Calcul en cours… », « Réessayer », reprise au réseau.
const BATTERIE = { id: 103, nom: 'Batterie Dyness PowerBrick 16 kWh', prix_vente: 40000, tva: 20, is_archived: false }
const HYBRIDE = { id: 104, nom: 'Onduleur hybride Deye 50kW Triphasé', prix_vente: 70000, tva: 20, is_archived: false }

function devisDeuxOptions() {
  const d = devisIndustriel('commercial')
  d.data.etude_params = { scenario: 'Les deux (Sans + Avec)' }
  d.data.lignes = [
    { ...d.data.lignes[0], variante: 'sans' }, { ...d.data.lignes[1], variante: 'sans' },
    { id: 3, produit: PANNEAU.id, designation: PANNEAU.nom, quantite: '120', prix_unitaire: '1000.00',
      taux_tva: '10.00', ordre: 2, type_ligne: 'produit', optionnelle: false, variante: 'avec' },
    { id: 4, produit: HYBRIDE.id, designation: HYBRIDE.nom, quantite: '1', prix_unitaire: '70000.00',
      taux_tva: '20.00', ordre: 3, type_ligne: 'produit', optionnelle: false, variante: 'avec' },
    { id: 5, produit: BATTERIE.id, designation: BATTERIE.nom, quantite: '1', prix_unitaire: '40000.00',
      taux_tva: '20.00', ordre: 4, type_ligne: 'produit', optionnelle: false, variante: 'avec' },
  ]
  return d
}

/** Réponse de l'aperçu : sur les lignes (71 kWc, 100 panneaux) ; libre (moteur : 120 panneaux). */
function apercuSelonLesLignes(corps) {
  const r = reponseContrat('ventes', 'etude_ci_preview')
  r.data.taille = corps.lignes ? { ...r.data.taille, nb_panneaux: 100, retenue_kwc: 71 }
    : { ...r.data.taille, nb_panneaux: 120, retenue_kwc: 85.2 }
  return Promise.resolve(r)
}

describe('T4-X6-008 / 007 — une valeur par option, celle des lignes du devis', () => {
  it('l’aperçu de l’édition porte les LIGNES ; la carte les décrit ; le moteur conseille à part', async () => {
    ventesApi.etudeCiPreview.mockImplementation(apercuSelonLesLignes)
    rendre()
    expect(await screen.findByTestId('ci-taille-retenue', {}, { timeout: 5000 })).toHaveTextContent('71')
    const surLignes = ventesApi.etudeCiPreview.mock.calls.map(([c]) => c).find((c) => c.lignes)
    expect(surLignes.devis).toBe(55)
    expect(surLignes.lignes.map((l) => [l.produit, l.quantite])).toEqual([[PANNEAU.id, '100'], [ONDULEUR.id, '1']])
    const conseil = await screen.findByTestId('ci-conseil-moteur')
    expect(conseil).toHaveTextContent('Le moteur conseille 120 panneaux')
    expect(conseil).toHaveTextContent('ce devis en vend 100')
    expect(screen.getByTestId('ci-conseil-appliquer')).toHaveTextContent('Appliquer')
  })

  it('devis à deux options : l’économie de l’offre réseau chiffre SES lignes seules ; un seul retour', async () => {
    stockApi.getProduits.mockResolvedValue({ data: [PANNEAU, ONDULEUR, BATTERIE, HYBRIDE] })
    ventesApi.getDevisById.mockResolvedValue(devisDeuxOptions())
    const eco = reponseContrat('ventes', 'economie_ci')
    eco.data.indicateurs = { ...eco.data.indicateurs, retour_dixieme_ans: 5.5 }
    ventesApi.economieCiPreview.mockResolvedValue(eco)
    rendre()
    await waitFor(() => expect(ventesApi.economieCiPreview).toHaveBeenCalled(), { timeout: 5000 })
    const [corps] = ventesApi.economieCiPreview.mock.calls.at(-1)
    expect(corps.lignes.map((l) => l.produit).sort()).toEqual([PANNEAU.id, ONDULEUR.id].sort())
    expect(await screen.findByTestId('ci-retour')).toHaveTextContent('5,5 ans')
  })
})

describe('T4-X6-010 / 011 — calcul en cours, échec, reprise', () => {
  it('pendant le calcul les cartes restent sous « Calcul en cours… » ; un échec offre « Réessayer »', async () => {
    const { container } = rendre()
    expect(await screen.findByTestId('ci-taille-retenue', {}, { timeout: 5000 })).toBeInTheDocument()
    let echouer
    ventesApi.etudeCiPreview.mockImplementation(() => new Promise((_ok, ko) => { echouer = ko }))
    fireEvent.change(container.querySelector('#gen-ci-kwh-0'), { target: { value: '6001' } })
    expect(await screen.findByTestId('ci-resultat-calcul', {}, { timeout: 3000 })).toHaveTextContent('Calcul en cours…')
    expect(screen.getByTestId('ci-taille-retenue')).toBeInTheDocument()
    await act(async () => { echouer(new Error('Network Error')) })
    expect(await screen.findByTestId('ci-resultat-erreur')).toHaveTextContent('indisponible')
    expect(screen.queryByTestId('ci-taille-retenue')).toBeNull()
    ventesApi.etudeCiPreview.mockResolvedValue(reponseContrat('ventes', 'etude_ci_preview'))
    fireEvent.click(screen.getByTestId('ci-resultat-reessayer'))
    expect(await screen.findByTestId('ci-taille-retenue', {}, { timeout: 3000 })).toBeInTheDocument()
  })

  it('au retour du réseau, un aperçu en échec est redemandé tout seul', async () => {
    ventesApi.etudeCiPreview.mockRejectedValue(new Error('Network Error'))
    rendre()
    expect(await screen.findByTestId('ci-resultat-erreur', {}, { timeout: 5000 })).toBeInTheDocument()
    ventesApi.etudeCiPreview.mockResolvedValue(reponseContrat('ventes', 'etude_ci_preview'))
    await act(async () => { window.dispatchEvent(new Event('online')) })
    expect(await screen.findByTestId('ci-taille-retenue', {}, { timeout: 3000 })).toBeInTheDocument()
  })
})
