import { describe, it, expect } from 'vitest'
import { peutVoirSalaires, PERM_SALAIRES_VOIR } from './permissions.js'

/* UX22 — Garde de permission « rémunération » (logique pure).
   L'onglet Rémunération d'un dossier employé ne doit apparaître QUE pour un
   compte portant `salaires_voir`. On teste la porte pure ici, indépendamment de
   tout rendu. */

describe('peutVoirSalaires — garde rémunération', () => {
  it('vrai quand la permission salaires_voir est présente', () => {
    expect(peutVoirSalaires([PERM_SALAIRES_VOIR])).toBe(true)
    expect(peutVoirSalaires(['autre', 'salaires_voir', 'x'])).toBe(true)
  })

  it('faux quand la permission est absente', () => {
    expect(peutVoirSalaires([])).toBe(false)
    expect(peutVoirSalaires(['journal_activite_voir'])).toBe(false)
  })

  it('tolère les entrées non-tableau sans lever', () => {
    expect(peutVoirSalaires(null)).toBe(false)
    expect(peutVoirSalaires(undefined)).toBe(false)
    expect(peutVoirSalaires('salaires_voir')).toBe(false)
    expect(peutVoirSalaires({ salaires_voir: true })).toBe(false)
  })

  it('exporte le code de permission attendu par le serveur', () => {
    expect(PERM_SALAIRES_VOIR).toBe('salaires_voir')
  })
})

/* Modélise la construction d'onglets du dossier employé (UX22) : la présence de
   l'onglet « remuneration » suit strictement la permission. On reproduit la
   règle pure (sans monter le composant) pour verrouiller le contrat. */
function tabsPourPermission(permissions) {
  const canSalaires = peutVoirSalaires(permissions)
  return [
    'identite', 'contrat', 'documents',
    ...(canSalaires ? ['remuneration'] : []),
    'habilitations', 'formations',
  ]
}

describe('onglets dossier employé selon permission', () => {
  it('inclut l’onglet rémunération avec la permission', () => {
    expect(tabsPourPermission(['salaires_voir'])).toContain('remuneration')
  })

  it('masque l’onglet rémunération sans la permission', () => {
    expect(tabsPourPermission([])).not.toContain('remuneration')
  })
})
