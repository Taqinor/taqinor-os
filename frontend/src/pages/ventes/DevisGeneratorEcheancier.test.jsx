// QJR624 (D-QJR5-10) — l'échéancier (acompte / matériel / solde) est éditable
// dans l'Édition complète : relu au chargement `?edit=`, modifié, et envoyé
// dans `entete.echeancier` de replace-lines (contrat QJR504, exemple COMMITTÉ
// `devis_replace_lines_entete.json` — PACT10). Un devis qui suit l'échéancier
// de la société n'en reçoit pas un figé en silence.
//
// Run : npx vitest run src/pages/ventes/DevisGeneratorEcheancier.test.jsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { documentContrat } from '../../test/fixtures/contractSamples'
import {
  echeancierAvecAcompte, echeancierVersSaisie, saisieVersEcheancier, saisieParDefaut,
  CONDITIONS_VIDES, conditionsVersEntete, echeancierFinanceur, LIBELLE_TRANCHE_FINANCEUR,
  erreurEcheancier,
} from '../../features/ventes/echeancierEdition'
import { useState } from 'react'
import CarteEcheancier from './generator/CarteEcheancier'
import { erreursConditions } from '../../features/ventes/echeancierEdition'
import { devisVersEtat, etatVersEcritures } from '../../features/ventes/quote/etatDevis'

vi.mock('../../api/crmApi', async () => (await import('../../test/mocksApiDevis.js')).crmApiAvecLead())
vi.mock('../../api/stockApi', async () => (await import('../../test/mocksApiDevis.js')).stockApiMock())
vi.mock('../../api/parametresApi', async () => (await import('../../test/mocksApiDevis.js')).parametresApiMock())
vi.mock('../../api/ventesApi', async () => (await import('../../test/mocksApiDevis.js')).ventesApiEdition())

import crmApi from '../../api/crmApi'
import stockApi from '../../api/stockApi'
import parametresApi from '../../api/parametresApi'
import ventesApi from '../../api/ventesApi'
import DevisGenerator from './DevisGenerator'
import { bancEdition, devisResidentielRouvert } from './devisGenerator.testHelpers.jsx'


const devisRouvert = (variante, echeancier) => devisResidentielRouvert(variante, { echeancier })

const { renderEdition } = bancEdition({ DevisGenerator, stockApi, crmApi, ventesApi })

// CIQ125 — un devis C&I sans consommation ni taille ne s'enregistre pas : le
// devis rouvert porte sa consommation déclarée (entrée v2).
const enMode = (r, mode) => ({
  data: {
    ...r.data, mode_installation: mode,
    etude_params: { ...r.data.etude_params, consommation: { kwh_annuel: 60000 } },
  },
})

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

// ══ AGNR37 — tranches qui ne totalisent pas le devis : enregistrement bloqué ══
describe('AGNR37 — échéancier hors total : aucune écriture', () => {
  it('tout en %, unités mixtes, tranche vide : la raison exacte', () => {
    const t = (valeur, unite = 'pct') => ({ valeur, unite })
    expect(erreurEcheancier([t('70'), t('60'), t('10')], 42600))
      .toBe('Total des tranches : 140 % — il doit faire 100 %.')
    expect(erreurEcheancier([t('10000', 'montant'), t('60'), t('10')], 42600))
      .toBe('Total des tranches : 93,5 % du TTC — il doit faire 100 %.')
    expect(erreurEcheancier([t('30'), t('60'), t('')], 42600)).toMatch(/^Tranche 3 vide/)
    expect(erreurEcheancier([t('30'), t('60'), t('10')], 42600)).toBeNull()
    expect(erreurEcheancier(null, 42600)).toBeNull()
  })

  const ouvrirEtSaisir = async (valeurs, unites = {}) => {
    parametresApi.getProfile.mockResolvedValue({ data: { payment_terms_effectifs: EFFECTIFS } })
    const rouvert = devisRouvert('exemple_envoye', ECHEANCIER_AGRICOLE)
    ventesApi.getDevisById.mockResolvedValue(rouvert)
    renderEdition(rouvert.data.id)
    await waitFor(() => expect(crmApi.getLead).toHaveBeenCalledWith(77))
    const carte = await screen.findByTestId('carte-echeancier')
    valeurs.forEach((v, i) => {
      fireEvent.change(carte.querySelector(`#gen-echeance-${i}`), { target: { value: v } })
    })
    for (const [i, unite] of Object.entries(unites)) {
      fireEvent.change(screen.getAllByLabelText(/^Unité — /)[i], { target: { value: unite } })
    }
    ventesApi.replaceLignesDevis.mockClear()
    await userEvent.click(await screen.findByRole('button', { name: /Enregistrer les modifications/ }))
    return carte
  }

  it.each([
    [['70', '60', '10'], {}, /Total des tranches : 140 % — il doit faire 100 %/],
    [['10000', '60', '10'], { 0: 'montant' }, /Total des tranches : [\d,]+ % du TTC — il doit faire 100 %/],
    [['30', '60', ''], {}, /Tranche 3 vide/],
  ])('%j ⇒ bloqué, raison sous la carte, bandeau nommé', async (valeurs, unites, raison) => {
    await ouvrirEtSaisir(valeurs, unites)
    expect(await screen.findByTestId('erreur-enregistrement'))
      .toHaveTextContent(/Échéancier de paiement : /)
    expect(screen.getByTestId('echeancier-somme')).toHaveTextContent(raison)
    expect(ventesApi.replaceLignesDevis).not.toHaveBeenCalled()
  })

  // CI #997 (4) — la règle « Σ = 100 % » est un refus 409 `ConflitEtat` côté
  // serveur (même message, même clé `echeancier`).
  it('refus 409 `echeancier` du serveur : affiché sous la carte', async () => {
    ventesApi.replaceLignesDevis.mockRejectedValueOnce({
      response: { status: 409, data: { echeancier: ['Total des tranches : 90 % — il doit faire 100 %.'] } },
    })
    await ouvrirEtSaisir(['30', '60', '10'])
    expect(await screen.findByTestId('echeancier-somme'))
      .toHaveTextContent('Total des tranches : 90 % — il doit faire 100 %.')
    expect(screen.getByTestId('erreur-enregistrement')).toHaveTextContent(/Échéancier de paiement/)
  })
})

// ══ CIQ226 — conditions déclarées : retenue, pénalités, caution, financeur ══
function HarnaisConditions({ onEtat }) {
  const [saisie, setSaisie] = useState(null)
  const [conditions, setConditions] = useState({ ...CONDITIONS_VIDES })
  onEtat({ saisie, conditions })
  return (
    <CarteEcheancier saisie={saisie} setSaisie={setSaisie} mode="commercial" effectifs={{}}
                     conditions={conditions} erreursConditions={erreursConditions(conditions)}
                     setCondition={(c, v) => setConditions((x) => ({ ...x, [c]: v }))}
                     clients={[{ id: 218, nom: 'Organisme financeur exemple' }]} />
  )
}

describe('CIQ226 — conditions demandées par le client', () => {
  it('pénalité sans plafond ⇒ erreur sous le champ ; avec plafond ⇒ aucune', () => {
    render(<HarnaisConditions onEtat={() => {}} />)
    fireEvent.change(screen.getByLabelText('Pénalités de retard (% par semaine)'), { target: { value: '0.5' } })
    expect(screen.getByTestId('erreur-condition-penalitePlafond')).toHaveTextContent('plafond est obligatoire')
    fireEvent.change(screen.getByLabelText('Plafond des pénalités (%)'), { target: { value: '10' } })
    expect(screen.queryByTestId('erreur-condition-penalitePlafond')).toBeNull()
  })

  it('échéancier organisme financeur 10/90 ⇒ projection exacte (forme du contrat)', () => {
    let etat = null
    render(<HarnaisConditions onEtat={(e) => { etat = e }} />)
    fireEvent.change(screen.getByLabelText('Organisme financeur'), { target: { value: '218' } })
    fireEvent.change(screen.getByLabelText('Acompte client (%)'), { target: { value: '10' } })
    fireEvent.click(screen.getByTestId('btn-echeancier-financeur'))
    expect(saisieVersEcheancier(etat.saisie)).toEqual([
      { libelle: 'Acompte client à la commande', type: 'acompte', unite: 'pct', pct_or_montant: 10,
        jalon: 'commande', payeur: 'client' },
      { libelle: LIBELLE_TRANCHE_FINANCEUR, type: 'solde', unite: 'pct', pct_or_montant: 90,
        jalon: 'reception_financeur', payeur: 'tiers' },
    ])
    expect(conditionsVersEntete(etat.conditions).tiers_payeur).toBe(218)
    // jamais « crédit-bail » à l'écran
    expect(screen.queryByText(/crédit-bail/i)).toBeNull()
    expect(echeancierFinanceur('10')).toHaveLength(2)
  })

  it('enregistrer → rouvrir → enregistrer sans toucher = en-tête identique', () => {
    const financeur = documentContrat('ventes', 'devis_replace_lines_entete').corps_financeur.entete
    const devis = {
      id: 9, mode_installation: 'commercial', taux_tva: '20.00', remise_globale: '0.00', lignes: [],
      etude_params: {}, echeancier: financeur.echeancier, tiers_payeur: financeur.tiers_payeur,
      reference_commande_client: financeur.reference_commande_client,
      retenue_garantie: { taux_pct: 5, liberation: 'reception_definitive' },
      penalites_retard_livraison: { taux_pct_par_semaine: 0.5, plafond_pct: 10 },
      caution: { nature: 'caution de bonne exécution', montant_ou_pct: 10, plafond: null },
    }
    const ecr1 = etatVersEcritures(devisVersEtat(devis), { entrees: {} })
    const devis2 = { ...devis, ...ecr1.entete }
    const ecr2 = etatVersEcritures(devisVersEtat(devis2), { entrees: {} })
    expect(ecr2.entete).toEqual(ecr1.entete)
    expect(ecr1.entete.retenue_garantie).toEqual(devis.retenue_garantie)
    expect(ecr1.entete.penalites_retard_livraison).toEqual(devis.penalites_retard_livraison)
    expect(ecr1.entete.tiers_payeur).toBe(financeur.tiers_payeur)
  })
})

