import { describe, it, expect, beforeEach } from 'vitest'
import {
  COCKPIT_VIEWS, applyCockpitView, loadSavedCockpitView, saveCockpitView,
} from './cockpitViews'

/* PUB43 — vues enregistrées un-clic : logique pure (filtre+tri figés + mémoire
   localStorage). */

const ROWS = [
  { id: 1, nom: 'Vidéo gagnante', thumbnail_kind: 'video', depense_mad: '500.00',
    signatures: 3, cost_per_signature_mad: '166.67',
    fatigue: { fired: false, severity: 'info' } },
  { id: 2, nom: 'Statique correcte', thumbnail_kind: 'image', depense_mad: '200.00',
    signatures: 1, cost_per_signature_mad: '200.00',
    fatigue: { fired: false, severity: 'info' } },
  { id: 3, nom: 'Fatiguée possible', thumbnail_kind: 'image', depense_mad: '400.00',
    signatures: 0, cost_per_signature_mad: null,
    fatigue: { fired: true, severity: 'avertissement' } },
  { id: 4, nom: 'En chute confirmée', thumbnail_kind: 'video', depense_mad: '1200.00',
    signatures: 0, cost_per_signature_mad: null,
    fatigue: { fired: true, severity: 'critique' } },
]

describe('COCKPIT_VIEWS', () => {
  it('expose Toutes + les 4 vues prédéfinies', () => {
    expect(COCKPIT_VIEWS.map(v => v.key)).toEqual(['toutes', 'top', 'fatigue', 'baisse', 'videos'])
  })
})

describe('applyCockpitView', () => {
  it('« toutes » renvoie la liste telle quelle (aucun filtre)', () => {
    expect(applyCockpitView(ROWS, 'toutes')).toEqual(ROWS)
  })

  it('« top » : signatures>0 triées par coût/signature croissant', () => {
    const out = applyCockpitView(ROWS, 'top')
    expect(out.map(r => r.id)).toEqual([1, 2])
  })

  it('« fatigue » : toute sévérité déclenchée, triée par dépense décroissante', () => {
    const out = applyCockpitView(ROWS, 'fatigue')
    expect(out.map(r => r.id)).toEqual([4, 3])
  })

  it('« baisse » : uniquement la sévérité critique', () => {
    const out = applyCockpitView(ROWS, 'baisse')
    expect(out.map(r => r.id)).toEqual([4])
  })

  it('« videos » : format vidéo uniquement, triée par coût/signature', () => {
    const out = applyCockpitView(ROWS, 'videos')
    expect(out.map(r => r.id)).toEqual([1, 4]) // 166.67 avant null
  })

  it('clé inconnue -> liste telle quelle (jamais une erreur)', () => {
    expect(applyCockpitView(ROWS, 'nope')).toEqual(ROWS)
  })

  it('liste absente -> tableau vide', () => {
    expect(applyCockpitView(null, 'top')).toEqual([])
    expect(applyCockpitView(undefined, 'top')).toEqual([])
  })
})

describe('loadSavedCockpitView / saveCockpitView', () => {
  beforeEach(() => { window.localStorage.clear() })

  it('round-trip : sauvegarde puis relit exactement le même état', () => {
    saveCockpitView({ tab: 'fatigue', sort: { key: 'depense_mad', dir: 'desc' } })
    expect(loadSavedCockpitView()).toEqual({ tab: 'fatigue', sort: { key: 'depense_mad', dir: 'desc' } })
  })

  it('rien d’enregistré -> null (jamais une erreur)', () => {
    expect(loadSavedCockpitView()).toBeNull()
  })

  it('valeur corrompue en localStorage -> null (dégradation silencieuse)', () => {
    window.localStorage.setItem('ae-cockpit-view', 'not-json{{{')
    expect(loadSavedCockpitView()).toBeNull()
  })
})
