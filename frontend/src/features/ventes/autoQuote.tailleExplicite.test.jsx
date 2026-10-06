// QJR602 (D-QJR5-13, fondateur 30/09/2026) — une taille EXPLICITE (cible
// tapée pour ce devis, ou `taille_souhaitee_kwc` du lead) est respectée TELLE
// QUELLE par le devis automatique : plus d'arrondi au palier de 5 kWc. Avant
// ce correctif, 6,5 kWc devenait 5 kWc (8 panneaux) au bouton, pendant que le
// serveur (POST /ventes/devis/auto/, tunnel, agent) en composait 10 : deux
// devis différents pour le même lead selon le chemin. Les paliers ne servent
// plus qu'au dimensionnement AUTOMATIQUE sans cible.
//
// Exécute le VRAI createAutoQuote ; seuls l'API et `autoFillLines` sont
// espionnés (l'espion prouve qu'aucune composition JS n'a lieu).
import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('../../api/ventesApi', () => ({
  default: {
    creerDevisAuto: vi.fn(() => Promise.resolve({ data: { id: 900 } })),
    createDevisAtomic: vi.fn(),
  },
}))
vi.mock('./solar', async (importOriginal) => {
  const original = await importOriginal()
  return { ...original, autoFillLines: vi.fn(() => []) }
})

import ventesApi from '../../api/ventesApi'
import { createAutoQuote } from './autoQuote'
import { autoFillLines, panneauxPourKwc, kwcPourPanneaux, PANEL_W_DEFAUT } from './solar'

beforeEach(() => { vi.clearAllMocks() })

describe('QJR602 — la taille explicite est souveraine (aucun palier de 5 kWc)', () => {
  it('résidentiel, lead à 6,5 kWc : le serveur reçoit 10 panneaux de 710 W (7,1 kWc), jamais 5 kWc', async () => {
    const id = await createAutoQuote({
      lead: { id: 1, type_installation: 'residentiel', taille_souhaitee_kwc: '6.5' },
      produits: [], discountStr: '0',
    })
    expect(id).toBe(900)
    const corps = ventesApi.creerDevisAuto.mock.calls[0][0]
    expect(panneauxPourKwc(6.5, PANEL_W_DEFAUT)).toBe(10)
    expect(corps.target_kwc).toBe(kwcPourPanneaux(10, PANEL_W_DEFAUT))
  })

  it('résidentiel, cible tapée 8 kWc pour CE devis : 12 panneaux (8,52 kWc), jamais le palier 10', async () => {
    await createAutoQuote({
      lead: { id: 2, type_installation: 'residentiel', taille_souhaitee_kwc: '6.5' },
      produits: [], discountStr: '0', targetKwc: '8',
    })
    const corps = ventesApi.creerDevisAuto.mock.calls[0][0]
    expect(corps.target_kwc).toBe(kwcPourPanneaux(panneauxPourKwc(8, PANEL_W_DEFAUT), PANEL_W_DEFAUT))
    expect(panneauxPourKwc(8, PANEL_W_DEFAUT)).toBe(12)
  })

  // CIQ127 — le C&I part au serveur : la taille souhaitée du lead y est lue
  // (souveraine, CIQ120) ; une cible tapée POUR CE devis part telle quelle.
  it.each(['industriel', 'commercial'])('%s, lead à 6,5 kWc : aucune composition JS, le serveur lit la taille', async (type) => {
    await createAutoQuote({
      lead: { id: 3, type_installation: type, taille_souhaitee_kwc: '6.5' },
      produits: [], discountStr: '0',
    })
    expect(autoFillLines).not.toHaveBeenCalled()
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
