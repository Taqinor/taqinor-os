import { describe, it, expect } from 'vitest'
import {
  peutEcrireFpa, peutAdministrerFpa,
  FPA_SAISIR, FPA_VALIDER, FPA_ADMINISTRER, FPA_CONSULTER_TOUT,
} from './permissions.js'

/* WIR198 — Garde de permission FP&A (logique pure), miroir de
   `FpaScopedPermission`/`ExigeFpaPermission` (apps/fpa/permissions.py).
   Le workflow soumettre/valider/rejeter (SaisiePage) exige l'un des codes
   d'ÉCRITURE ; la gouvernance des cycles (AdministrationPage, WIR199) exige
   spécifiquement `fpa_administrer`. */

describe('peutEcrireFpa — garde workflow budget (soumettre/valider/rejeter)', () => {
  it('vrai avec fpa_saisir, fpa_valider ou fpa_administrer', () => {
    expect(peutEcrireFpa([FPA_SAISIR])).toBe(true)
    expect(peutEcrireFpa([FPA_VALIDER])).toBe(true)
    expect(peutEcrireFpa([FPA_ADMINISTRER])).toBe(true)
    expect(peutEcrireFpa(['autre', FPA_VALIDER, 'x'])).toBe(true)
  })

  it('faux avec fpa_consulter_tout seul (droit de lecture élargie, jamais d’écriture)', () => {
    expect(peutEcrireFpa([FPA_CONSULTER_TOUT])).toBe(false)
  })

  it('faux sans aucun code fpa_*', () => {
    expect(peutEcrireFpa([])).toBe(false)
    expect(peutEcrireFpa(['stock_creer'])).toBe(false)
  })

  it('tolère les entrées non-tableau sans lever', () => {
    expect(peutEcrireFpa(null)).toBe(false)
    expect(peutEcrireFpa(undefined)).toBe(false)
    expect(peutEcrireFpa('fpa_saisir')).toBe(false)
  })
})

describe('peutAdministrerFpa — garde gouvernance cycles/départements', () => {
  it('vrai uniquement avec fpa_administrer', () => {
    expect(peutAdministrerFpa([FPA_ADMINISTRER])).toBe(true)
  })

  it('faux avec fpa_saisir ou fpa_valider seuls (insuffisant pour administrer)', () => {
    expect(peutAdministrerFpa([FPA_SAISIR])).toBe(false)
    expect(peutAdministrerFpa([FPA_VALIDER])).toBe(false)
    expect(peutAdministrerFpa([FPA_CONSULTER_TOUT])).toBe(false)
  })

  it('tolère les entrées non-tableau sans lever', () => {
    expect(peutAdministrerFpa(null)).toBe(false)
    expect(peutAdministrerFpa(undefined)).toBe(false)
  })
})
