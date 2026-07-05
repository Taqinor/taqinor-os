import { describe, it, expect } from 'vitest'
import {
  optionsFrom, buildBinTree, countBinsInTree, sortPickListLignesByBin,
  pickListProgress, colisProgress, PUTAWAY_STATUTS,
} from './magasin'

/* Tests purs du module Magasin (XSTK1) : arborescence des casiers, tri des
   lignes de prélèvement par casier, progressions pick-list/colis. Aucune
   dépendance React — vérifie la logique en isolation du rendu. */

describe('optionsFrom', () => {
  it('transforme un map de statuts en options {value,label}', () => {
    expect(optionsFrom(PUTAWAY_STATUTS)).toContainEqual({ value: 'range', label: 'Rangé' })
  })
})

describe('buildBinTree', () => {
  const bins = [
    { id: 1, emplacement: 10, emplacement_nom: 'Dépôt central', zone: 'A', allee: '01', casier: '01', code: 'A-01-01', archived: false },
    { id: 2, emplacement: 10, emplacement_nom: 'Dépôt central', zone: 'A', allee: '01', casier: '02', code: 'A-01-02', archived: false },
    { id: 3, emplacement: 10, emplacement_nom: 'Dépôt central', zone: 'B', allee: '01', casier: '01', code: 'B-01-01', archived: false },
    { id: 4, emplacement: 20, emplacement_nom: 'Camionnette 1', zone: null, allee: null, casier: null, code: 'CAM1', archived: false },
    { id: 5, emplacement: 10, emplacement_nom: 'Dépôt central', zone: 'A', allee: '01', casier: '03', code: 'A-01-03', archived: true },
  ]

  it('regroupe emplacement -> zone -> allée -> casiers', () => {
    const tree = buildBinTree(bins)
    expect(tree).toHaveLength(2)
    const depot = tree.find((e) => e.label === 'Dépôt central')
    expect(depot.zones).toHaveLength(2)
    const zoneA = depot.zones.find((z) => z.label === 'A')
    expect(zoneA.allees).toHaveLength(1)
    expect(zoneA.allees[0].bins).toHaveLength(2) // A-01-01, A-01-02 (archivé exclu)
  })

  it('exclut les casiers archivés par défaut', () => {
    const tree = buildBinTree(bins)
    const total = countBinsInTree(tree)
    expect(total).toBe(4)
  })

  it('inclut les casiers archivés avec includeArchived', () => {
    const tree = buildBinTree(bins, { includeArchived: true })
    expect(countBinsInTree(tree)).toBe(5)
  })

  it('tolère une liste vide/undefined', () => {
    expect(buildBinTree()).toEqual([])
    expect(buildBinTree(null)).toEqual([])
    expect(countBinsInTree(undefined)).toBe(0)
  })

  it('gère les casiers sans zone/allée (regroupement "Sans zone"/"Sans allée")', () => {
    const tree = buildBinTree(bins)
    const camionnette = tree.find((e) => e.label === 'Camionnette 1')
    expect(camionnette.zones[0].label).toBe('Sans zone')
    expect(camionnette.zones[0].allees[0].label).toBe('Sans allée')
  })
})

describe('sortPickListLignesByBin', () => {
  it('trie par ordre croissant, les lignes sans ordre en dernier', () => {
    const lignes = [
      { id: 3, ordre: undefined },
      { id: 1, ordre: 5 },
      { id: 2, ordre: 1 },
    ]
    const sorted = sortPickListLignesByBin(lignes)
    expect(sorted.map((l) => l.id)).toEqual([2, 1, 3])
  })

  it('ne mute pas le tableau original', () => {
    const lignes = [{ id: 1, ordre: 2 }, { id: 2, ordre: 1 }]
    const copy = [...lignes]
    sortPickListLignesByBin(lignes)
    expect(lignes).toEqual(copy)
  })

  it('tolère undefined', () => {
    expect(sortPickListLignesByBin()).toEqual([])
  })
})

describe('pickListProgress', () => {
  it('compte les lignes prélevées', () => {
    const lignes = [{ preleve: true }, { preleve: false }, { preleve: true }]
    expect(pickListProgress(lignes)).toEqual({ done: 2, total: 3, pct: 67 })
  })

  it('renvoie 0% pour une liste vide', () => {
    expect(pickListProgress([])).toEqual({ done: 0, total: 0, pct: 0 })
    expect(pickListProgress()).toEqual({ done: 0, total: 0, pct: 0 })
  })
})

describe('colisProgress', () => {
  it('compte les lignes contrôlées', () => {
    const lignes = [{ controle_ok: true }, { controle_ok: true }]
    expect(colisProgress(lignes)).toEqual({ done: 2, total: 2, pct: 100 })
  })

  it('tolère undefined', () => {
    expect(colisProgress()).toEqual({ done: 0, total: 0, pct: 0 })
  })
})
