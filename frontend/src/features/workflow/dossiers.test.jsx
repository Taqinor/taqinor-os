import { describe, it, expect } from 'vitest'
import {
  routeForLien, estEnRetard, filtrerDossiers, prioriteTone,
  TYPE_DOSSIER_OPTIONS, STATUT_DOSSIER_OPTIONS, PRIORITE_DOSSIER_OPTIONS,
} from './dossiers'

describe('routeForLien (NTWFL17/19)', () => {
  it('résout une cible connue vers sa route réelle', () => {
    expect(routeForLien('crm.lead', 42)).toBe('/crm/leads/42')
    expect(routeForLien('ventes.devis', 7)).toBe('/ventes/devis?id=7')
    expect(routeForLien('sav.ticket', 3)).toBe('/sav?id=3')
    expect(routeForLien('installations.installation', 9)).toBe('/chantiers?id=9')
  })

  it('est insensible à la casse de la clé', () => {
    expect(routeForLien('CRM.LEAD', 1)).toBe('/crm/leads/1')
  })

  it('renvoie null pour une cible sans mapping connu (jamais un lien mort)', () => {
    expect(routeForLien('rh.employe', 1)).toBeNull()
    expect(routeForLien('', 1)).toBeNull()
    expect(routeForLien(undefined, 1)).toBeNull()
  })
})

describe('estEnRetard (NTWFL21)', () => {
  const AUJOURD_HUI = '2026-09-20'

  it('vrai si échéance dépassée et statut ouvert', () => {
    expect(estEnRetard({ statut: 'ouvert', echeance: '2026-09-01' }, AUJOURD_HUI)).toBe(true)
  })

  it('faux si échéance future', () => {
    expect(estEnRetard({ statut: 'ouvert', echeance: '2026-12-01' }, AUJOURD_HUI)).toBe(false)
  })

  it('faux si le dossier est fermé (clos/abandonné), même en retard', () => {
    expect(estEnRetard({ statut: 'clos', echeance: '2026-09-01' }, AUJOURD_HUI)).toBe(false)
    expect(estEnRetard({ statut: 'abandonne', echeance: '2026-09-01' }, AUJOURD_HUI)).toBe(false)
  })

  it('faux si aucune échéance', () => {
    expect(estEnRetard({ statut: 'ouvert', echeance: null }, AUJOURD_HUI)).toBe(false)
  })
})

describe('filtrerDossiers (NTWFL22)', () => {
  const AUJOURD_HUI = '2026-09-20'
  const DOSSIERS = [
    { id: 1, statut: 'ouvert', priorite: 'haute', echeance: '2026-09-01' },
    { id: 2, statut: 'ouvert', priorite: 'basse', echeance: '2026-12-01' },
    { id: 3, statut: 'clos', priorite: 'haute', echeance: '2026-01-01' },
  ]

  it('sans filtre, renvoie tout tel quel', () => {
    expect(filtrerDossiers(DOSSIERS, {}, AUJOURD_HUI)).toHaveLength(3)
  })

  it('filtre par priorité', () => {
    const r = filtrerDossiers(DOSSIERS, { priorite: 'haute' }, AUJOURD_HUI)
    expect(r.map((d) => d.id)).toEqual([1, 3])
  })

  it('combine priorité + en retard uniquement ("Mes réclamations en retard")', () => {
    const r = filtrerDossiers(
      DOSSIERS, { priorite: 'haute', enRetardSeulement: true }, AUJOURD_HUI,
    )
    expect(r.map((d) => d.id)).toEqual([1])
  })

  it('tolère une liste absente/malformée', () => {
    expect(filtrerDossiers(null, {}, AUJOURD_HUI)).toEqual([])
    expect(filtrerDossiers(undefined, { priorite: 'haute' }, AUJOURD_HUI)).toEqual([])
  })
})

describe('prioriteTone', () => {
  it('mappe chaque priorité connue', () => {
    expect(prioriteTone('basse')).toBe('neutral')
    expect(prioriteTone('normale')).toBe('info')
    expect(prioriteTone('haute')).toBe('warning')
    expect(prioriteTone('critique')).toBe('danger')
  })

  it('repli neutre sur une valeur inconnue', () => {
    expect(prioriteTone('inconnue')).toBe('neutral')
  })
})

describe('catalogues fermés', () => {
  it('reflètent les choix serveur (core.models.Dossier)', () => {
    expect(TYPE_DOSSIER_OPTIONS.map((o) => o.value)).toEqual([
      'reclamation_complexe', 'onboarding_grand_compte', 'litige',
      'projet_transverse', 'autre',
    ])
    expect(STATUT_DOSSIER_OPTIONS.map((o) => o.value)).toEqual([
      'ouvert', 'en_cours', 'en_attente', 'clos', 'abandonne',
    ])
    expect(PRIORITE_DOSSIER_OPTIONS.map((o) => o.value)).toEqual([
      'basse', 'normale', 'haute', 'critique',
    ])
  })
})
