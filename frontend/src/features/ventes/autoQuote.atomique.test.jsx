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

const { createAutoQuote } = autoQuote

beforeEach(() => {
  vi.clearAllMocks()
})

describe('CIQ127 — devis automatique non résidentiel : UN appel serveur', () => {
  it('agricole : UN appel serveur /ventes/devis/auto/, aucun createDevisAtomic, alertes rendues', async () => {
    const alertes = [{ code: 'pvgis_indisponible', champ: 'production', message: 'Irradiation indisponible' }]
    api.creerDevisAuto.mockResolvedValueOnce({ data: { id: 777, statut: 'brouillon', alertes } })
    const lead = { id: 7, type_installation: 'agricole', pompe_hmt_m: 60, pompe_debit_m3h: 12 }
    const onAlertes = vi.fn()
    const id = await createAutoQuote({ lead, produits: [], discountStr: '5', dispatch: vi.fn(), onAlertes })
    expect(id).toBe(777)
    expect(api.creerDevisAuto).toHaveBeenCalledTimes(1)
    expect(api.creerDevisAuto.mock.calls[0][0]).toEqual({ lead: 7, remise_globale: '5' })
    expect(api.createDevisAtomic).not.toHaveBeenCalled()
    expect(onAlertes).toHaveBeenCalledWith(alertes)
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
