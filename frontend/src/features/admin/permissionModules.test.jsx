/* SOL12 — l'éditeur de rôles ne propose que les permissions des modules que la
   société a réellement, sans jamais retirer un droit déjà accordé. */
import { describe, it, expect } from 'vitest'

import {
  codeDUnModuleEteint, filtrerCodesAffichables,
} from './permissionModules'

const CODES = [
  'crm_voir', 'crm_gerer',
  'mrp_voir',            // vertical parqué (édition solaire)
  'pos_voir',            // module optionnel éteint à la création (SOL8)
  'installation_voir',   // préfixe ≠ clé de module
  'equipement_voir',     // appartient à `sav`
  'roles_gerer',         // fondation : aucun module
  'prix_achat_voir',     // donnée sensible : aucun module
]

const MODULES = {
  crm_voir: 'crm',
  crm_gerer: 'crm',
  mrp_voir: 'mrp',
  pos_voir: 'pos',
  installation_voir: 'installations',
  equipement_voir: 'sav',
}

describe('filtrerCodesAffichables (SOL12)', () => {
  it('aucun module éteint : la liste est rendue telle quelle', () => {
    expect(filtrerCodesAffichables(CODES, MODULES, [])).toEqual(CODES)
    expect(filtrerCodesAffichables(CODES, MODULES, undefined)).toEqual(CODES)
  })

  it('retire les codes des modules éteints ou parqués', () => {
    const vus = filtrerCodesAffichables(CODES, MODULES, ['mrp', 'pos'])
    expect(vus).not.toContain('mrp_voir')
    expect(vus).not.toContain('pos_voir')
    expect(vus).toContain('crm_voir')
  })

  it('respecte la correspondance SERVEUR, jamais un préfixe deviné', () => {
    // `installation_*` appartient à `installations` : éteindre `installations`
    // doit le retirer, alors qu'un filtre par préfixe ne l'aurait jamais vu.
    const vus = filtrerCodesAffichables(CODES, MODULES, ['installations'])
    expect(vus).not.toContain('installation_voir')
    // Et `equipement_voir` suit `sav`, pas un module « equipement ».
    const vus2 = filtrerCodesAffichables(CODES, MODULES, ['sav'])
    expect(vus2).not.toContain('equipement_voir')
    const vus3 = filtrerCodesAffichables(CODES, MODULES, ['equipement'])
    expect(vus3).toContain('equipement_voir')
  })

  it('ne masque JAMAIS un code sans module connu', () => {
    const vus = filtrerCodesAffichables(
      CODES, MODULES, ['crm', 'mrp', 'pos', 'installations', 'sav'])
    expect(vus).toContain('roles_gerer')
    expect(vus).toContain('prix_achat_voir')
  })

  it('garde un code DÉJÀ porté par le rôle édité (droit jamais supprimé)', () => {
    const vus = filtrerCodesAffichables(
      CODES, MODULES, ['mrp'], ['mrp_voir'])
    expect(vus).toContain('mrp_voir')
  })

  it('sans correspondance servie (backend ancien), rien n\'est masqué', () => {
    expect(filtrerCodesAffichables(CODES, undefined, ['mrp', 'pos']))
      .toEqual(CODES)
  })

  it('conserve l\'ordre d\'entrée', () => {
    const vus = filtrerCodesAffichables(CODES, MODULES, ['mrp'])
    expect(vus).toEqual(CODES.filter((c) => c !== 'mrp_voir'))
  })
})

describe('codeDUnModuleEteint (SOL12)', () => {
  it('signale un code hérité d\'un module éteint', () => {
    expect(codeDUnModuleEteint('mrp_voir', MODULES, ['mrp'])).toBe(true)
    expect(codeDUnModuleEteint('crm_voir', MODULES, ['mrp'])).toBe(false)
    expect(codeDUnModuleEteint('roles_gerer', MODULES, ['mrp'])).toBe(false)
  })
})
