import { describe, it, expect, beforeEach } from 'vitest'
import {
  personaForRoleNom, queueViewForRole, sortMaFileItems,
  getPersonaOverride, setPersonaOverride, getQuickWinsPref, setQuickWinsPref,
} from './queueViews'

/* VX211 — « Ma file » par persona + départage « victoires rapides ». Tests
   des fonctions PURES : jamais un filtre (tous les items d'entrée ressortent
   dans la sortie), seul l'ORDRE change selon le rôle. */

beforeEach(() => {
  window.localStorage.clear()
})

describe('personaForRoleNom (VX211)', () => {
  it('reconnaît les 4 personas par mot-clé', () => {
    expect(personaForRoleNom('Comptable')).toBe('comptable')
    expect(personaForRoleNom('Technicien responsable')).toBe('terrain')
    expect(personaForRoleNom('Installateur')).toBe('terrain')
    expect(personaForRoleNom('Directeur')).toBe('direction')
    expect(personaForRoleNom('Commercial responsable')).toBe('commercial')
  })
  it('rôle non reconnu → default (jamais une exception)', () => {
    expect(personaForRoleNom('Magasinier')).toBe('default')
    expect(personaForRoleNom(null)).toBe('default')
    expect(personaForRoleNom(undefined)).toBe('default')
  })
})

describe('sortMaFileItems (VX211) — un commercial voit Relances en tête', () => {
  const items = [
    { kind: 'approbation', urgency: 'overdue', due: null, id: 1 },
    { kind: 'relance', urgency: 'today', due: '2026-08-01', id: 2 },
    { kind: 'mention', urgency: 'today', due: null, id: 3 },
  ]

  it('commercial : relance en tête même si moins urgente que approbation', () => {
    const sorted = sortMaFileItems(items, { roleNom: 'Commercial' })
    expect(sorted[0].kind).toBe('relance')
  })

  it('comptable : approbation en tête', () => {
    const sorted = sortMaFileItems(items, { roleNom: 'Comptable' })
    expect(sorted[0].kind).toBe('approbation')
  })

  it('rôle non reconnu : ordre GLOBAL par urgence pur (comportement VX83 inchangé)', () => {
    const sorted = sortMaFileItems(items, { roleNom: 'Magasinier' })
    // Toujours en_retard d'abord (approbation), c'est le tri d'urgence pur.
    expect(sorted[0].kind).toBe('approbation')
  })

  it('jamais un filtre : tous les items d’entrée ressortent', () => {
    const sorted = sortMaFileItems(items, { roleNom: 'Commercial' })
    expect(sorted).toHaveLength(3)
    expect(sorted.map((it) => it.id).sort()).toEqual([1, 2, 3])
  })
})

describe('sortMaFileItems — départage « victoires rapides » (VX211)', () => {
  const sameUrgency = [
    { kind: 'devis_expire', urgency: 'overdue', due: null, effort_estime: 'eleve', id: 'A' },
    { kind: 'mention', urgency: 'overdue', due: null, effort_estime: 'faible', id: 'B' },
  ]

  it('option désactivée (défaut) : ordre par persona/urgence inchangé, jamais par effort', () => {
    // Même persona 'default' (ordre global ALL_KINDS) pour ne tester QUE
    // l'effet du départage effort, pas l'effet de la persona.
    const sorted = sortMaFileItems(sameUrgency, { roleNom: null, quickWinsFirst: false })
    // Sans départage effort, l'ordre suit le rang de kind par défaut
    // (mention avant devis_expire dans ALL_KINDS) — stable et déterministe.
    expect(sorted.map((it) => it.id)).toEqual(['B', 'A'])
  })

  it('option activée : l’item « faible » précède l’« eleve » à urgence égale', () => {
    // Force le MÊME rang de kind pour isoler le départage effort seul.
    const equalKind = [
      { kind: 'activite', urgency: 'overdue', due: null, effort_estime: 'eleve', id: 'A' },
      { kind: 'activite', urgency: 'overdue', due: null, effort_estime: 'faible', id: 'B' },
    ]
    const sorted = sortMaFileItems(equalKind, { roleNom: null, quickWinsFirst: true })
    expect(sorted.map((it) => it.id)).toEqual(['B', 'A'])
  })
})

describe('surcharge persistée localStorage (VX211)', () => {
  it('la surcharge persona gagne sur le rôle auto-détecté', () => {
    expect(getPersonaOverride()).toBeNull()
    setPersonaOverride('direction')
    expect(getPersonaOverride()).toBe('direction')
    expect(queueViewForRole('Commercial')[0]).toBe('approbation')
    setPersonaOverride(null)
    expect(getPersonaOverride()).toBeNull()
    expect(queueViewForRole('Commercial')[0]).toBe('relance')
  })

  it('la préférence « victoires rapides » persiste', () => {
    expect(getQuickWinsPref()).toBe(false)
    setQuickWinsPref(true)
    expect(getQuickWinsPref()).toBe(true)
    setQuickWinsPref(false)
    expect(getQuickWinsPref()).toBe(false)
  })
})
