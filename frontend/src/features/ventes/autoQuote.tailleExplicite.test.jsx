// QJR602 (D-QJR5-13, fondateur 30/09/2026) — une taille EXPLICITE (cible
// tapée pour ce devis, ou `taille_souhaitee_kwc` du lead) est respectée TELLE
// QUELLE par le devis automatique : plus d'arrondi au palier de 5 kWc. Avant
// ce correctif, 6,5 kWc devenait 5 kWc (8 panneaux) au bouton, pendant que le
// serveur (POST /ventes/devis/auto/, tunnel, agent) en composait 10 : deux
// devis différents pour le même lead selon le chemin. Les paliers ne servent
// plus qu'au dimensionnement AUTOMATIQUE sans cible.
//
// Exécute le VRAI createAutoQuote ; seule l'API est espionnée. ADEV69 —
// l'espion sur `autoFillLines` est retiré avec la fonction (second composeur
// supprimé) : « aucune composition JS » est désormais structurel, et
// `createDevisAtomic` jamais appelé reste la preuve du chemin serveur.
import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('../../api/ventesApi', () => ({
  default: {
    creerDevisAuto: vi.fn(() => Promise.resolve({ data: { id: 900 } })),
    createDevisAtomic: vi.fn(),
  },
}))

import ventesApi from '../../api/ventesApi'
import { createAutoQuote } from './autoQuote'
import { exempleContrat } from '../../test/fixtures/contractSamples'

beforeEach(() => { vi.clearAllMocks() })

describe('QJR602 — la taille explicite est souveraine (aucun palier de 5 kWc)', () => {
  // T4-X1-004 — la taille tapée part TELLE QUELLE : l'écran ne l'arrondit plus
  // au panneau de 710 W supposé (3 → 3,55), le serveur compose avec ses vrais
  // panneaux.
  it('résidentiel, lead à 6,5 kWc : le serveur reçoit 6,5 kWc tel quel, jamais 5 kWc ni un arrondi d écran', async () => {
    const id = await createAutoQuote({
      lead: { id: 1, type_installation: 'residentiel', taille_souhaitee_kwc: '6.5' },
      produits: [], discountStr: '0',
    })
    expect(id).toBe(900)
    const corps = ventesApi.creerDevisAuto.mock.calls[0][0]
    expect(corps.target_kwc).toBe(6.5)
  })

  it('résidentiel, cible tapée 3 kWc pour CE devis : 3 kWc envoyés, jamais 3,55 ni le palier 5', async () => {
    await createAutoQuote({
      lead: { id: 2, type_installation: 'residentiel', taille_souhaitee_kwc: '6.5' },
      produits: [], discountStr: '0', targetKwc: '3',
    })
    const corps = ventesApi.creerDevisAuto.mock.calls[0][0]
    expect(corps.target_kwc).toBe(3)
  })

  // CIQ127 — le C&I part au serveur : la taille souhaitée du lead y est lue
  // (souveraine, CIQ120) ; une cible tapée POUR CE devis part telle quelle.
  it.each(['industriel', 'commercial'])('%s, lead à 6,5 kWc : aucune composition JS, le serveur lit la taille', async (type) => {
    await createAutoQuote({
      lead: { id: 3, type_installation: type, taille_souhaitee_kwc: '6.5' },
      produits: [], discountStr: '0',
    })
    expect(ventesApi.createDevisAtomic).not.toHaveBeenCalled()
    expect(ventesApi.creerDevisAuto.mock.calls[0][0]).toEqual({ lead: 3, remise_globale: '0' })
  })

  it.each(['industriel', 'commercial'])('%s, cible 6,5 kWc pour CE devis : target_kwc 6,5 tel quel', async (type) => {
    await createAutoQuote({
      lead: { id: 4, type_installation: type }, produits: [], discountStr: '0', targetKwc: '6.5',
    })
    expect(ventesApi.creerDevisAuto.mock.calls[0][0]).toEqual({ lead: 4, remise_globale: '0', target_kwc: 6.5 })
  })
})

// AGNR34 (D-AGNR-1 option (a)) — le corps que reçoit le serveur : ni douze
// mois dérivés sous `factures_mensuelles_reelles`, ni conso calculée au
// navigateur ; le serveur lit les deux factures du lead (source `facture_hiver_ete`).
describe('AGNR34 — devis auto résidentiel : deux factures, aucune série fabriquée', () => {
  it('lead hiver 800 / été 1 600 « été différent » : seul le distributeur déclaré voyage', async () => {
    await createAutoQuote({
      lead: { id: 5, type_installation: 'residentiel', facture_hiver: '800', facture_ete: '1600',
              ete_differente: true, distributeur: 'onee' },
      produits: [], discountStr: '0',
    })
    const corps = ventesApi.creerDevisAuto.mock.calls[0][0]
    expect(corps).toEqual({ lead: 5, remise_globale: '0', etude_params: { distributeur: 'onee' } })
  })
})

describe('T4-X1-004 — la taille réelle est dite quand elle diffère de la cible tapée', () => {
  it('3 kWc tapés, devis servi à 3,55 kWc : une alerte nomme les deux tailles et pourquoi', async () => {
    // La réponse servie (contrat committé), à 3,55 kWc et avec l'alerte « Taille imposée » que le serveur pose.
    ventesApi.creerDevisAuto.mockResolvedValueOnce({ data: { ...exempleContrat('ventes', 'assistant_devis_cree'), kwc: 3.55, alertes: [{ code: 'taille_demandee', message: 'Taille imposée pour ce devis : 3 kWc' }] } })
    const onAlertes = vi.fn()
    await createAutoQuote({ lead: { id: 4, type_installation: 'residentiel' }, produits: [], discountStr: '0', targetKwc: '3', onAlertes })
    const alertes = onAlertes.mock.calls[0][0]
    expect(alertes).toHaveLength(2)
    expect(alertes[1].message).toMatch(/3 kWc.*3,55 kWc.*panneaux est entier/)
  })

  it('deux options servies à 3,55 kWc : chacune nommée ; taille servie égale à la cible : aucune alerte en plus', async () => {
    const { alerteTailleArrondie } = await import('./autoQuote')
    const deux = alerteTailleArrondie(3, { options: [{ variante: 'sans', libelle: 'Sans batterie', kwc: 3.55 }, { variante: 'avec', libelle: 'Avec batterie', kwc: 3.55 }] })
    expect(deux.message).toContain('Sans batterie : 3,55 kWc')
    expect(deux.message).toContain('Avec batterie : 3,55 kWc')
    expect(alerteTailleArrondie(3.55, { kwc: 3.55 })).toBeNull()
    expect(alerteTailleArrondie(3, { })).toBeNull()
    expect(alerteTailleArrondie(0, { kwc: 3.55 })).toBeNull()
  })

  it('« jamais en dessous de la demande » n’est dit que si chaque taille servie est ≥ la cible', async () => {
    const { alerteTailleArrondie } = await import('./autoQuote')
    expect(alerteTailleArrondie(3, { kwc: 3.55 }).message).toContain('(jamais en dessous de la demande)')
    const dessous = alerteTailleArrondie(3, { kwc: 2.84 })
    expect(dessous.message).toContain('le devis est à 2,84 kWc')
    expect(dessous.message).not.toMatch(/jamais en dessous/)
    const mixte = alerteTailleArrondie(3, { options: [{ variante: 'sans', libelle: 'Sans batterie', kwc: 2.84 }, { variante: 'avec', libelle: 'Avec batterie', kwc: 3.55 }] })
    expect(mixte.message).not.toMatch(/jamais en dessous/)
  })
})
