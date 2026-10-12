// COUV-HOR (29/09/2026) — rouvrir un devis ne doit plus réécrire une
// consommation annuelle FAUSSE. DEV-202609-0113 portait conso_annuelle =
// 198 000 MAD ÷ 1,20 = 165 000 kWh (repli sans barème du devis auto) : `?edit=`
// la réaffichait en kWh « tapés », l'enregistrement la faisait passer AVANT
// la dérivation des factures, et l'estampillait 'onee' — elle revenait donc à
// chaque sauvegarde (avec une dérive ×12 : 110 000 → 110 004).
//
// Ce test REND l'écran réel en édition et lit ce que l'enregistrement envoie
// à `PATCH /ventes/devis/<id>/etude-params/` — aucune lecture de source.
import { describe, it, expect, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { estimerMois, consoAnnuelleDepuisFactures } from '../../features/ventes/solar'

vi.mock('../../api/crmApi', async () => (await import('../../test/mocksApiDevis.js')).crmApiMock())
vi.mock('../../api/stockApi', async () => (await import('../../test/mocksApiDevis.js')).stockApiMock())
vi.mock('../../api/parametresApi', async () => (await import('../../test/mocksApiDevis.js')).parametresApiMock())
vi.mock('../../api/ventesApi', async () => (await import('../../test/mocksApiDevis.js')).ventesApiEdition())

import stockApi from '../../api/stockApi'
import ventesApi from '../../api/ventesApi'
import DevisGenerator from './DevisGenerator'
import { PANNEAU, declarerBeforeEachDevis, makeDevisStore, renderEditionPage } from './devisGenerator.testHelpers.jsx'

const ONDULEUR = {
  id: 102, nom: 'Onduleur réseau 30kW Triphasé', prix_vente: 36000, tva: 20,
  is_archived: false, prix_achat: 25000,
}

// Les 12 factures de DEV-202609-0113 (hiver 11 000, été 22 000 MAD/mois).
const FACTURES_KHALID = estimerMois(11000, 22000)
const CONSO_BAREME = consoAnnuelleDepuisFactures(FACTURES_KHALID, 'onee')

function devisRouvert(etudeParams) {
  return {
    data: {
      // Seul un brouillon se rouvre (DEV-202609-0113 l'était encore à 17:01).
      id: 336, reference: 'DEV-202609-0113', statut: 'brouillon', modifiable: true, raison_non_modifiable: '', revision_possible: false, is_active: true, lead: null, client: 9,
      mode_installation: 'residentiel', taux_tva: '20.00', remise_globale: '0',
      etude_params: etudeParams,
      lignes: [
        { id: 1, produit: PANNEAU.id, designation: PANNEAU.nom, quantite: '42',
          prix_unitaire: '1200.00', taux_tva: '10.00', ordre: 0,
          type_ligne: 'produit', optionnelle: false },
        { id: 2, produit: ONDULEUR.id, designation: ONDULEUR.nom, quantite: '1',
          prix_unitaire: '30000.00', taux_tva: '20.00', ordre: 1,
          type_ligne: 'produit', optionnelle: false },
      ],
    },
  }
}

const makeStore = () => makeDevisStore('normal', 'Commercial')

function renderEdition() {
  return renderEditionPage(DevisGenerator, makeStore(), '336', 'APRES-ENREGISTREMENT')
}

// Ce que l'enregistrement envoie à l'endpoint de fusion `etude-params`.
async function enregistrerEtLireEtude() {
  const bouton = await screen.findByRole('button', { name: /Enregistrer les modifications/ })
  await userEvent.click(bouton)
  await waitFor(() => expect(ventesApi.patchEtudeParams).toHaveBeenCalled())
  const [id, cles] = ventesApi.patchEtudeParams.mock.calls.at(-1)
  expect(id).toBe(336)
  return cles
}

declarerBeforeEachDevis({ stockApi, ventesApi, produits: [PANNEAU, ONDULEUR], ecritures: true })

describe('COUV-HOR — la conso annuelle d\'un devis rouvert', () => {
  it('DEV-202609-0113 : la conso ÷ 1,20 des factures est RE-DÉRIVÉE au barème, jamais réécrite', async () => {
    // ERR-QAH-PROP-JS-CONSO-FACTURE-TOTALE — barème COMPLET (lignes fixes +
    // TPPAN retirées), le chiffre du serveur : 120 972 (122 007 énergie seule).
    expect(CONSO_BAREME).toBe(120972)
    ventesApi.getDevisById.mockResolvedValue(devisRouvert({
      scenario: 'Sans batterie',
      conso_annuelle: 165000,               // 198 000 ÷ 1,20
      factures_mensuelles_reelles: FACTURES_KHALID,
    }))
    renderEdition()
    const cles = await enregistrerEtLireEtude()
    expect(cles.conso_annuelle).toBe(CONSO_BAREME)
    // Calculée ICI au barème du distributeur affiché : l'étiquette le dit.
    expect(cles.distributeur).toBe('onee')
  })

  it('une conso SAISIE (qui ne descend pas des factures) repart exacte, sans dérive ×12 ni distributeur fabriqué', async () => {
    ventesApi.getDevisById.mockResolvedValue(devisRouvert({
      scenario: 'Sans batterie',
      conso_annuelle: 110000,               // tapée : ni 122 007 ni 165 000
      factures_mensuelles_reelles: FACTURES_KHALID,
    }))
    renderEdition()
    const cles = await enregistrerEtLireEtude()
    expect(cles.conso_annuelle).toBe(110000)   // AVANT : 110 004
    expect('distributeur' in cles).toBe(false) // AVANT : 'onee' estampillé
  })

  it('des kWh RETAPÉS par le vendeur restent souverains', async () => {
    ventesApi.getDevisById.mockResolvedValue(devisRouvert({
      scenario: 'Sans batterie',
      conso_annuelle: 110000,
      factures_mensuelles_reelles: FACTURES_KHALID,
    }))
    renderEdition()
    const champ = await screen.findByLabelText('Consommation réelle (kWh/mois)')
    await waitFor(() => expect(champ).toHaveValue(9167))
    await userEvent.clear(champ)
    await userEvent.type(champ, '9000')
    const cles = await enregistrerEtLireEtude()
    expect(cles.conso_annuelle).toBe(108000)
    expect('distributeur' in cles).toBe(false)
  })
})
