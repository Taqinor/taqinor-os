import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import {
  ajouterArc, arcDepuisApi, centreNoeud, grapheDepuisApi, libelleCondition,
  nouveauNoeud, payloadArc, payloadNoeud, prochainOrdre, segmentArc,
} from './journeyGraph'

vi.mock('../../api/marketingApi', () => ({
  default: {
    unwrapList: (res) => (Array.isArray(res?.data) ? res.data : (res?.data?.results ?? [])),
    noeudsJourney: {
      list: vi.fn(() => Promise.resolve({ data: [] })),
      create: vi.fn(() => Promise.resolve({ data: { id: 1 } })),
      update: vi.fn(() => Promise.resolve({ data: {} })),
      remove: vi.fn(() => Promise.resolve({ data: {} })),
    },
    arcsJourney: {
      list: vi.fn(() => Promise.resolve({ data: [] })),
      create: vi.fn(() => Promise.resolve({ data: { id: 9 } })),
      update: vi.fn(() => Promise.resolve({ data: {} })),
      remove: vi.fn(() => Promise.resolve({ data: {} })),
    },
  },
}))

// ── NTMKT13 — sérialisation nœuds/arcs (logique pure, sans DOM) ────────────

describe('grapheDepuisApi — relit exactement le contrat NTMKT12', () => {
  it('convertit positions et config, trie les arcs par ordre', () => {
    const g = grapheDepuisApi(
      [{ id: 1, sequence: 5, type_noeud: 'attente', libelle: 'A', position_x: '30', position_y: 12, config: { delai_jours: 3 } }],
      [
        { id: 8, source: 1, cible: 2, condition: 'toujours', ordre: 2 },
        { id: 7, source: 1, cible: 3, condition: 'a_ouvert', ordre: 1 },
      ],
    )
    expect(g.noeuds[0]).toEqual({
      id: 1, sequence: 5, type_noeud: 'attente', libelle: 'A',
      x: 30, y: 12, config: { delai_jours: 3 },
    })
    expect(g.arcs.map(a => a.id)).toEqual([7, 8])
  })

  it('tolère des listes vides / une config nulle', () => {
    expect(grapheDepuisApi(null, null)).toEqual({ noeuds: [], arcs: [] })
    expect(arcDepuisApi({}).condition).toBe('toujours')
  })
})

describe('payloadNoeud / payloadArc — jamais de company dans le corps', () => {
  it('sérialise un nœud avec des positions entières', () => {
    const body = payloadNoeud(nouveauNoeud('action', 12.7, 40.2), 5)
    expect(body).toEqual({
      sequence: 5, type_noeud: 'action', libelle: 'Action (message / CRM)',
      position_x: 13, position_y: 40, config: {},
    })
    expect(body.company).toBeUndefined()
  })

  it("vide la valeur d'un arc dont la condition n'en porte pas", () => {
    expect(payloadArc({ source: 1, cible: 2, condition: 'toujours', valeur: 'x', ordre: 1 }).valeur).toBe('')
    expect(payloadArc({ source: 1, cible: 2, condition: 'tag_present', valeur: 'vip', ordre: 1 }).valeur).toBe('vip')
  })
})

describe('ajouterArc — 2 conditions différentes depuis le même nœud', () => {
  const base = []
  it('refuse la boucle sur soi-même et les doublons', () => {
    expect(ajouterArc(base, { source: 1, cible: 1 })).toBe(base)
    const un = ajouterArc(base, { source: 1, cible: 2, condition: 'a_ouvert' })
    expect(un).toHaveLength(1)
    expect(ajouterArc(un, { source: 1, cible: 2, condition: 'a_ouvert' })).toBe(un)
  })

  it('empile deux embranchements sortants avec des ordres croissants', () => {
    let arcs = ajouterArc([], { source: 1, cible: 2, condition: 'a_ouvert' })
    arcs = ajouterArc(arcs, { source: 1, cible: 3, condition: 'toujours' })
    expect(arcs.map(a => [a.cible, a.condition, a.ordre]))
      .toEqual([[2, 'a_ouvert', 1], [3, 'toujours', 2]])
    expect(prochainOrdre(arcs, 1)).toBe(3)
  })
})

describe('géométrie du canevas', () => {
  it('ancre les arêtes au centre des nœuds', () => {
    expect(centreNoeud({ x: 0, y: 0 })).toEqual({ x: 75, y: 27 })
    const noeuds = [{ id: 1, x: 0, y: 0 }, { id: 2, x: 200, y: 100 }]
    expect(segmentArc(noeuds, { source: 1, cible: 2 }))
      .toEqual({ x1: 75, y1: 27, x2: 275, y2: 127 })
    expect(segmentArc(noeuds, { source: 1, cible: 99 })).toBeNull()
  })

  it('affiche la valeur des conditions qui en portent une', () => {
    expect(libelleCondition({ condition: 'a_clique' })).toBe('A cliqué')
    expect(libelleCondition({ condition: 'score_seuil', valeur: '50' }))
      .toBe('Score >= seuil : 50')
  })
})

// ── Rendu : le graphe rouvert affiche les mêmes nœuds/arcs ─────────────────

describe('JourneyBuilder — rouvrir affiche le même graphe', () => {
  beforeEach(() => vi.clearAllMocks())

  it('rend les nœuds persistés et le libellé de chaque connexion', async () => {
    const marketingApi = (await import('../../api/marketingApi')).default
    marketingApi.noeudsJourney.list.mockResolvedValueOnce({
      data: [
        { id: 1, sequence: 5, type_noeud: 'declencheur', libelle: 'Départ', position_x: 10, position_y: 10 },
        { id: 2, sequence: 5, type_noeud: 'action', libelle: 'Email', position_x: 200, position_y: 10 },
        { id: 3, sequence: 5, type_noeud: 'sortie', libelle: 'Fin', position_x: 200, position_y: 150 },
      ],
    })
    marketingApi.arcsJourney.list.mockResolvedValueOnce({
      data: [
        { id: 7, source: 1, cible: 2, condition: 'a_ouvert', ordre: 1 },
        { id: 8, source: 1, cible: 3, condition: 'toujours', ordre: 2 },
      ],
    })
    const { default: JourneyBuilder } = await import('./JourneyBuilder')
    render(<JourneyBuilder sequenceId={5} sequenceNom="Nurture" />)
    // Le canevas SVG est la seule zone inspectée : les mêmes libellés existent
    // aussi dans le sélecteur de condition de la palette (strict-mode).
    await waitFor(() => expect(screen.getByRole('application')).toBeInTheDocument())
    const canevas = within(screen.getByRole('application'))
    await waitFor(() => expect(canevas.getByText('Départ')).toBeInTheDocument())
    expect(canevas.getByText('Email')).toBeInTheDocument()
    expect(canevas.getByText('Fin')).toBeInTheDocument()
    expect(canevas.getByText('A ouvert')).toBeInTheDocument()
    expect(canevas.getByText('Toujours')).toBeInTheDocument()
  })
})
