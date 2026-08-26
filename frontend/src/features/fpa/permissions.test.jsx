import { describe, it, expect } from 'vitest'
import {
  peutEcrireFpa, peutAdministrerFpa,
  FPA_SAISIR, FPA_VALIDER, FPA_ADMINISTRER, FPA_CONSULTER_TOUT,
} from './permissions.js'

/* WIR198/199 — Garde de permission FP&A (logique pure), miroir de
   `FpaScopedPermission`/`ExigeFpaPermission` (apps/fpa/permissions.py).
   Le workflow soumettre/valider/rejeter (SaisiePage) exige l'un des codes
   d'ÉCRITURE ; la gouvernance des cycles (AdministrationPage, WIR199) exige
   spécifiquement `fpa_administrer`.

   Revue Fable (post-merge) — le repli OrLegacy manquait : `porte_un_code_fpa`
   (apps/fpa/permissions.py) laisse passer un compte SANS rôle fin (palier
   responsable/admin — superuser sans rôle inclus, `menu_tier` lui pose
   toujours 'admin') même sans code fpa_*. Les codes `fpa_*` n'étant entrés au
   catalogue QUE dans ce batch, sans ce repli AUCUN compte existant ne les
   porte et tout le workflow FP&A serait invisible au déploiement. */

describe('peutEcrireFpa — garde workflow budget (soumettre/valider/rejeter)', () => {
  it('vrai avec fpa_saisir, fpa_valider ou fpa_administrer (rôle fin)', () => {
    expect(peutEcrireFpa([FPA_SAISIR])).toBe(true)
    expect(peutEcrireFpa([FPA_VALIDER])).toBe(true)
    expect(peutEcrireFpa([FPA_ADMINISTRER])).toBe(true)
    expect(peutEcrireFpa(['autre', FPA_VALIDER, 'x'])).toBe(true)
  })

  it('faux avec fpa_consulter_tout seul (droit de lecture élargie, jamais d’écriture)', () => {
    expect(peutEcrireFpa([FPA_CONSULTER_TOUT])).toBe(false)
  })

  it('un rôle fin SANS code fpa_* reste refusé, quel que soit le palier (jamais un repli légacy pour un rôle fin)', () => {
    expect(peutEcrireFpa(['stock_creer'])).toBe(false)
    expect(peutEcrireFpa(['stock_creer'], 'admin')).toBe(false)
    expect(peutEcrireFpa(['stock_creer'], 'responsable')).toBe(false)
  })

  it('sans tier connu, une liste vide est refusée (jamais un octroi par défaut)', () => {
    expect(peutEcrireFpa([])).toBe(false)
  })

  it('tolère les entrées non-tableau comme une liste vide, sans lever', () => {
    expect(peutEcrireFpa(null)).toBe(false)
    expect(peutEcrireFpa(undefined)).toBe(false)
    expect(peutEcrireFpa('fpa_saisir')).toBe(false)
  })

  describe('repli légacy (permissions vides + palier responsable/admin — miroir de porte_un_code_fpa)', () => {
    it('vrai pour un compte SANS rôle fin au palier responsable ou admin (superuser sans rôle inclus, menu_tier = admin)', () => {
      expect(peutEcrireFpa([], 'responsable')).toBe(true)
      expect(peutEcrireFpa([], 'admin')).toBe(true)
      expect(peutEcrireFpa(null, 'admin')).toBe(true)
      expect(peutEcrireFpa(undefined, 'responsable')).toBe(true)
    })

    it('faux pour un compte sans rôle fin au palier normal (hors responsable/admin)', () => {
      expect(peutEcrireFpa([], 'normal')).toBe(false)
      expect(peutEcrireFpa([], undefined)).toBe(false)
    })
  })
})

describe('peutAdministrerFpa — garde gouvernance cycles/départements', () => {
  it('vrai uniquement avec fpa_administrer (rôle fin)', () => {
    expect(peutAdministrerFpa([FPA_ADMINISTRER])).toBe(true)
  })

  it('faux avec fpa_saisir ou fpa_valider seuls (insuffisant pour administrer, rôle fin)', () => {
    expect(peutAdministrerFpa([FPA_SAISIR])).toBe(false)
    expect(peutAdministrerFpa([FPA_VALIDER])).toBe(false)
    expect(peutAdministrerFpa([FPA_CONSULTER_TOUT])).toBe(false)
  })

  it('un rôle fin SANS fpa_administrer reste refusé même au palier admin (jamais un repli légacy pour un rôle fin)', () => {
    expect(peutAdministrerFpa([FPA_SAISIR], 'admin')).toBe(false)
  })

  it('tolère les entrées non-tableau comme une liste vide, sans lever', () => {
    expect(peutAdministrerFpa(null)).toBe(false)
    expect(peutAdministrerFpa(undefined)).toBe(false)
  })

  describe('repli légacy (permissions vides + palier responsable/admin — ExigeFpaPermission utilise le MÊME porte_un_code_fpa)', () => {
    it('vrai pour un compte SANS rôle fin au palier responsable ou admin — la gouvernance suit le même repli que l’écriture', () => {
      expect(peutAdministrerFpa([], 'responsable')).toBe(true)
      expect(peutAdministrerFpa([], 'admin')).toBe(true)
    })

    it('faux pour un compte sans rôle fin au palier normal', () => {
      expect(peutAdministrerFpa([], 'normal')).toBe(false)
      expect(peutAdministrerFpa([], undefined)).toBe(false)
    })
  })
})
