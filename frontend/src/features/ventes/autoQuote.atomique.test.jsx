// QJR543 — le « Devis automatique » agricole / industriel / commercial se crée
// en UN appel atomique (POST /ventes/devis/atomic/) qui porte son étude
// (projetée par QJR542 : clés ECRAN seulement) et son scénario. Plus jamais
// createDevis + N addLigneDevis (non atomique, brouillon partiel, étude
// ignorée car en lecture seule sur POST /devis/).
//
// Exécute le VRAI createAutoQuote ; seules la composition et la sélection de
// pompe (solar.js) sont remplacées par des valeurs fixes.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const slice = vi.hoisted(() => ({
  createDevis: vi.fn(() => ({ type: 'test/createDevis' })),
  addLigneDevis: vi.fn(() => ({ type: 'test/addLigneDevis' })),
}))
vi.mock('./store/ventesSlice', () => slice)

const api = vi.hoisted(() => ({
  createDevisAtomic: vi.fn(),
  creerDevisAuto: vi.fn(),
  createDevis: vi.fn(),
  addLigneDevis: vi.fn(),
}))
vi.mock('../../api/ventesApi', () => ({ default: api }))

vi.mock('./solar', async (importOriginal) => {
  const original = await importOriginal()
  const ligne = (produit, designation, quantite, ttc) => ({
    produit: String(produit), designation, quantite: String(quantite),
    prix_unit_ttc: ttc, taux_tva: 20,
  })
  return {
    ...original,
    autoFillPompage: vi.fn(() => [
      ligne(1, 'Pompe immergée OSP 30-5', 1, 12000),
      ligne(2, 'Variateur VEICHI SI22', 1, 6000),
      ligne(3, 'Panneau 710W', 8, 1100),
    ]),
    pompageSelection: vi.fn(() => ({
      cv: 5.5, kw: 4, pump: { nom: 'OSP 30-5' }, debitHmt: 12.4, m3Jour: 86.8,
      dims: { champKwc: 5.68 },
    })),
    optimalKwcByPayback: vi.fn(() => ({ nbPanneaux: 20 })),
    autoFillLines: vi.fn(() => [
      ligne(10, 'Panneau 710W', 20, 1100),
      ligne(11, 'Onduleur réseau 15 kW', 1, 18000),
      ligne(12, 'Onduleur hybride 15 kW', 1, 30000),
      ligne(13, 'Batterie lithium 10 kWh', 1, 40000),
    ]),
  }
})

import { createAutoQuote } from './autoQuote'

// Les clés ECRAN déclarées par le schéma serveur — lues dans le SOURCE
// Python, jamais une seconde liste recopiée à la main.
const HERE = dirname(fileURLToPath(import.meta.url))
const SCHEMA_PY = readFileSync(
  join(HERE, '../../../../backend/django_core/apps/ventes/domain/etude_schema.py'), 'utf8')
const ECRAN = new Set(
  // `\s*` après `_cle(` : une déclaration peut passer à la ligne
  // (`'saisies_economie_pompage': _cle(\n        (dict,), ECRAN, …`).
  [...SCHEMA_PY.matchAll(/^ {4}'([a-z0-9_]+)': _cle\(\s*\([^)]*\),\s*ECRAN\b/gm)].map(m => m[1]))

const horsSchema = (obj) => Object.keys(obj || {}).filter(k => !ECRAN.has(k))

beforeEach(() => {
  vi.clearAllMocks()
  api.createDevisAtomic.mockResolvedValue({ data: { id: 501 } })
})

describe('QJR543 — devis automatique non résidentiel : UN appel atomique', () => {
  it('le schéma ECRAN est bien lu (le test se protège de sa propre extraction)', () => {
    expect(ECRAN.size).toBeGreaterThan(40)
    expect(ECRAN.has('m3_jour')).toBe(true)
    expect(ECRAN.has('scenario')).toBe(true)
  })

  it('agricole : createDevisAtomic ×1 avec lignes + étude typée, jamais addLigneDevis', async () => {
    const lead = {
      id: 7, type_installation: 'agricole', pompe_cv: 5.5, pompe_hmt_m: 60, pompe_debit_m3h: 12,
    }
    const id = await createAutoQuote({ lead, produits: [], discountStr: '5', dispatch: vi.fn() })
    expect(id).toBe(501)
    expect(api.createDevisAtomic).toHaveBeenCalledTimes(1)
    expect(slice.addLigneDevis).not.toHaveBeenCalled()
    expect(slice.createDevis).not.toHaveBeenCalled()
    expect(api.addLigneDevis).not.toHaveBeenCalled()
    const corps = api.createDevisAtomic.mock.calls[0][0]
    expect(corps.lead).toBe(7)
    expect(corps.statut).toBe('brouillon')
    expect(corps.mode_installation).toBe('agricole')
    expect(corps.remise_globale).toBe('5')
    expect(corps.lignes).toHaveLength(3)
    expect(corps.lignes.map(l => l.ordre)).toEqual([0, 1, 2])
    expect(corps.lignes[0]).toMatchObject({ produit: 1, quantite: '1', remise: '0', taux_tva: '20' })
    expect(horsSchema(corps.etude_params)).toEqual([])
    expect(corps.etude_params.m3_jour).toBe(86.8)
    expect(typeof corps.etude_params.pompe_cv).toBe('number')
    expect(corps.etude_params).not.toHaveProperty('pompe_nom')
  })

  it('industriel : createDevisAtomic ×1, scénario « Sans batterie » + taux_autoconso, aucune clé brute', async () => {
    const lead = { id: 8, type_installation: 'industriel', facture_hiver: '20000', distributeur: 'onee' }
    const onEtude = vi.fn()
    const id = await createAutoQuote({ lead, produits: [], discountStr: '0', dispatch: vi.fn(), onEtude })
    expect(id).toBe(501)
    expect(api.createDevisAtomic).toHaveBeenCalledTimes(1)
    expect(slice.addLigneDevis).not.toHaveBeenCalled()
    const corps = api.createDevisAtomic.mock.calls[0][0]
    expect(corps.mode_installation).toBe('industriel')
    expect(corps.lignes).toHaveLength(4)
    expect(horsSchema(corps.etude_params)).toEqual([])
    expect(corps.etude_params.scenario).toBe('Sans batterie')
    expect(typeof corps.etude_params.taux_autoconso).toBe('number')
    for (const brute of ['kwc', 'prix_kwc', 'economies_annuelles', 'prod_mensuelle']) {
      expect(corps.etude_params).not.toHaveProperty(brute)
    }
    // L'appelant voit toujours les chiffres clés AVANT enregistrement.
    expect(onEtude).toHaveBeenCalledTimes(1)
    expect(typeof onEtude.mock.calls[0][0].economies_annuelles).toBe('number')
  })

  it('rejet de la création atomique → l\'erreur remonte, aucun autre appel', async () => {
    api.createDevisAtomic.mockRejectedValueOnce({ response: { status: 400, data: { detail: 'non' } } })
    const lead = { id: 9, type_installation: 'agricole', pompe_cv: 5.5 }
    await expect(createAutoQuote({ lead, produits: [], discountStr: '0', dispatch: vi.fn() }))
      .rejects.toBeTruthy()
    expect(api.createDevisAtomic).toHaveBeenCalledTimes(1)
    expect(api.addLigneDevis).not.toHaveBeenCalled()
    expect(api.createDevis).not.toHaveBeenCalled()
    expect(slice.addLigneDevis).not.toHaveBeenCalled()
    expect(slice.createDevis).not.toHaveBeenCalled()
  })
})
