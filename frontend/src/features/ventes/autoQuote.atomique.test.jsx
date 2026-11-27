// CIQ127 — le « Devis automatique » de TOUS les marchés non résidentiels part
// au SERVEUR : un seul appel `POST /ventes/devis/auto/` (agricole AGR124,
// commercial / industriel CIQ120), jamais `createDevisAtomic`, aucune
// composition ni étude JavaScript. Un 422 rend le message du serveur tel quel
// (champ nommé) ; ses `alertes` vont à `onAlertes`.
// (Remplace QJR543 « UN appel atomique » pour le C&I, ainsi que les tests du
// balayage C&I écran — autoQuote.balayageCI / etudeConsoCI / consoKwh — dont
// les fonctions sont supprimées : le dimensionnement C&I est couvert côté
// serveur par les tests CIQ107-CIQ122.)
//
// Exécute le VRAI createAutoQuote ; seule l'API HTTP est simulée.
import { describe, it, expect, vi, beforeEach } from 'vitest'

const api = vi.hoisted(() => ({
  createDevisAtomic: vi.fn(),
  creerDevisAuto: vi.fn(),
  createDevis: vi.fn(),
  addLigneDevis: vi.fn(),
}))
vi.mock('../../api/ventesApi', () => ({ default: api }))

import * as autoQuote from './autoQuote'
import { exempleContrat, reponseContrat } from '../../test/fixtures/contractSamples'

const { createAutoQuote } = autoQuote

beforeEach(() => {
  vi.clearAllMocks()
})

describe('CIQ127 — devis automatique non résidentiel : UN appel serveur', () => {
  it('agricole : UN appel serveur /ventes/devis/auto/, aucun createDevisAtomic, alertes rendues', async () => {
    // COP2-W3 — réponse = échantillon du contrat (id, alertes), jamais un littéral tapé ici.
    const { id: idContrat, alertes } = exempleContrat('ventes', 'assistant_devis_cree')
    api.creerDevisAuto.mockResolvedValueOnce(reponseContrat('ventes', 'assistant_devis_cree'))
    const lead = { id: 7, type_installation: 'agricole', pompe_hmt_m: 60, pompe_debit_m3h: 12 }
    const onAlertes = vi.fn()
    const id = await createAutoQuote({ lead, produits: [], discountStr: '5', dispatch: vi.fn(), onAlertes })
    expect(id).toBe(idContrat)
    expect(api.creerDevisAuto).toHaveBeenCalledTimes(1)
    expect(api.creerDevisAuto.mock.calls[0][0]).toEqual({ lead: 7, remise_globale: '5' })
    expect(api.createDevisAtomic).not.toHaveBeenCalled()
    expect(onAlertes).toHaveBeenCalledWith(alertes)
  })

  it('ADEV123 — résidentiel : les alertes du serveur (suppositions) vont aussi à onAlertes', async () => {
    const { alertes } = exempleContrat('ventes', 'assistant_devis_cree')
    api.creerDevisAuto.mockResolvedValueOnce(reponseContrat('ventes', 'assistant_devis_cree'))
    const onAlertes = vi.fn()
    const onResultat = vi.fn()
    await createAutoQuote({ lead: { id: 11, type_installation: 'residentiel', facture_hiver: '600' },
      discountStr: '0', onAlertes, onResultat })
    expect(onAlertes).toHaveBeenCalledWith(alertes)
    expect(onResultat).toHaveBeenCalledTimes(1)
  })

  it('agricole : un 422 du serveur remonte TEL QUEL (message et champ nommé)', async () => {
    const detail = "Relevé du point d'eau requis avant devis (D-AGR-4) : niveau d'eau et débit du forage à mesurer lors d'une visite."
    api.creerDevisAuto.mockRejectedValueOnce({
      response: { status: 422, data: { detail, field: 'niveau_statique_m' } },
    })
    const lead = { id: 9, type_installation: 'agricole' }
    await expect(createAutoQuote({ lead, produits: [], discountStr: '0', dispatch: vi.fn() }))
      .rejects.toEqual({ detail, field: 'niveau_statique_m' })
    expect(api.createDevisAtomic).not.toHaveBeenCalled()
  })

  it('industriel : un seul appel /ventes/devis/auto/, aucun createDevisAtomic, aucune étude locale', async () => {
    api.creerDevisAuto.mockResolvedValueOnce({ data: { id: 501, statut: 'brouillon' } })
    const lead = { id: 8, type_installation: 'industriel', facture_hiver: '20000', distributeur: 'onee' }
    const onEtude = vi.fn()
    const onAlertes = vi.fn()
    const id = await createAutoQuote({
      lead, produits: [], discountStr: '0', dispatch: vi.fn(), onEtude, onAlertes,
    })
    expect(id).toBe(501)
    expect(api.creerDevisAuto).toHaveBeenCalledTimes(1)
    // Rien n'est calculé à l'écran : ni taille, ni étude, ni lignes.
    expect(api.creerDevisAuto.mock.calls[0][0]).toEqual({ lead: 8, remise_globale: '0' })
    expect(api.createDevisAtomic).not.toHaveBeenCalled()
    expect(api.addLigneDevis).not.toHaveBeenCalled()
    expect(onEtude).not.toHaveBeenCalled()
    expect(onAlertes).toHaveBeenCalledWith([])
  })

  it('commercial : la cible saisie POUR CE devis part en target_kwc, telle quelle', async () => {
    api.creerDevisAuto.mockResolvedValueOnce({ data: { id: 502 } })
    const lead = { id: 12, type_installation: 'commercial' }
    await createAutoQuote({ lead, produits: [], discountStr: '2', dispatch: vi.fn(), targetKwc: '37.5' })
    expect(api.creerDevisAuto.mock.calls[0][0]).toEqual({ lead: 12, remise_globale: '2', target_kwc: 37.5 })
  })

  it('AGNR39 — agricole : une cible transmise par erreur ne part jamais (le champ découle de la pompe)', async () => {
    api.creerDevisAuto.mockResolvedValueOnce({ data: { id: 503 } })
    const lead = { id: 14, type_installation: 'agricole' }
    await createAutoQuote({ lead, produits: [], discountStr: '0', dispatch: vi.fn(), targetKwc: '99' })
    expect(api.creerDevisAuto.mock.calls[0][0]).toEqual({ lead: 14, remise_globale: '0' })
  })

  // T4-X1-011 — un 500 (ou aucune réponse) accusait « la fiche du lead » : la
  // seconde tentative, fiche inchangée, créait le devis. Une panne SERVEUR le dit.
  it.each([
    ['résidentiel', { id: 21, type_installation: 'residentiel', facture_hiver: '600' }],
    ['commercial', { id: 22, type_installation: 'commercial' }],
  ])('T4-X1-011 — %s : un 500 dit que le serveur n’a pas répondu, sans accuser la fiche', async (_nom, lead) => {
    api.creerDevisAuto.mockRejectedValueOnce({ response: { status: 500, data: {} } })
    const refus = await createAutoQuote({ lead, discountStr: '0', dispatch: vi.fn() })
      .then(() => null, (e) => e)
    expect(refus.serveur).toBe(true)
    expect(refus.detail).toMatch(/serveur/)
    expect(refus.detail).not.toMatch(/vérifiez la fiche/)
  })

  it('T4-X1-011 — aucune réponse (réseau, délai) : même message serveur ; un 409 nommant un champ garde la fiche', async () => {
    api.creerDevisAuto.mockRejectedValueOnce(Object.assign(new Error('Network Error'), { code: 'ERR_NETWORK' }))
    const reseau = await createAutoQuote({ lead: { id: 23, type_installation: 'residentiel', facture_hiver: '600' }, discountStr: '0' })
      .then(() => null, (e) => e)
    expect(reseau.serveur).toBe(true)
    api.creerDevisAuto.mockRejectedValueOnce({ response: { status: 409, data: { detail: 'Facture manquante.', field: 'facture_hiver' } } })
    const champ = await createAutoQuote({ lead: { id: 24, type_installation: 'residentiel' }, discountStr: '0' })
      .then(() => null, (e) => e)
    expect(champ).toEqual({ detail: 'Facture manquante.', field: 'facture_hiver' })
  })

  it('ACAL1325 — industriel / commercial / résidentiel : la création coupe le toast global (l\'écran dit seul le résultat) ; un délai dépassé = « peut-être créé »', async () => {
    for (const type of ['industriel', 'commercial', 'residentiel']) {
      api.creerDevisAuto.mockClear()
      api.creerDevisAuto.mockResolvedValueOnce({ data: { id: 136 } })
      await createAutoQuote({ lead: { id: 312, type_installation: type, facture_hiver: '20000' }, discountStr: '0' })
      expect(api.creerDevisAuto.mock.calls[0][1]).toMatchObject({ suppressErrorToast: true })
    }
    api.creerDevisAuto.mockRejectedValueOnce(Object.assign(new Error('timeout'), { code: 'ECONNABORTED' }))
    const delai = await createAutoQuote({ lead: { id: 312, type_installation: 'industriel' }, discountStr: '0' })
      .then(() => null, (e) => e)
    expect(delai.delaiDepasse).toBe(true)
  })

  it('commercial : un 422 du moteur C&I remonte TEL QUEL (champ nommé), aucun devis créé', async () => {
    const detail = 'Consommation du site absente : renseignez les kWh mensuels ou une taille.'
    api.creerDevisAuto.mockRejectedValueOnce({
      response: { status: 422, data: { detail, field: 'consommation' } },
    })
    const lead = { id: 13, type_installation: 'commercial' }
    await expect(createAutoQuote({ lead, produits: [], discountStr: '0', dispatch: vi.fn() }))
      .rejects.toEqual({ detail, field: 'consommation' })
    expect(api.createDevisAtomic).not.toHaveBeenCalled()
  })

  it('les helpers du balayage C&I écran sont supprimés', () => {
    for (const nom of [['parametres', 'BalayageCI'], ['consoMensuelle', 'EtudeCI'], ['kwhMensuels', 'LeadPro']]
      .map((p) => p.join(''))) {
      expect(autoQuote).not.toHaveProperty(nom)
    }
  })
})
