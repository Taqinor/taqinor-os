import { describe, it, expect, vi } from 'vitest'

// ASAV48 — l'annulation d'une édition de statut en masse lit le résultat du
// serveur (traites / echecs) et ne propose « Annuler » que si le retour est
// dans `statuts_suivants`. Faux serveur qui applique une machine d'états.

vi.mock('../../api/savApi', () => ({ default: {} }))
vi.mock('../../api/axios', () => ({ default: { get: vi.fn(() => Promise.resolve({ data: [] })) } }))
vi.mock('../../api/installationsApi', () => ({ default: {} }))

import { parseBulkResult, executerEditionStatut, annulerEditionStatut } from './TicketsPage'

const GRAPHE = {
  nouveau: ['en_cours', 'planifie'],
  planifie: ['en_cours', 'nouveau'],
  en_cours: ['planifie', 'resolu'],
  resolu: ['cloture', 'en_cours'],
}

function fauxServeur(tickets) {
  const etat = new Map(tickets.map((t) => [t.id, t.statut]))
  return {
    etat,
    actionsGroupeesTickets: vi.fn(async (ids, _op, { statut }) => {
      const traites = []
      const echecs = []
      for (const id of ids) {
        if (GRAPHE[etat.get(id)]?.includes(statut)) { etat.set(id, statut); traites.push(id) }
        else echecs.push({ id, raison: `Transition ${etat.get(id)} → ${statut} refusée.` })
      }
      return { data: { traites, echecs, nb_traites: traites.length, nb_echecs: echecs.length } }
    }),
    getTicket: vi.fn(async (id) => ({ data: { id, statut: etat.get(id), statuts_suivants: GRAPHE[etat.get(id)] ?? [] } })),
  }
}

const lignes = [
  { id: 1, reference: 'SAV-1', statut: 'nouveau' },
  { id: 2, reference: 'SAV-2', statut: 'nouveau' },
]

describe('ASAV48 — édition de statut en masse et annulation', () => {
  it('Planifié → En cours : « Annuler » proposé (retour permis)', async () => {
    const rows = lignes.map((l) => ({ ...l, statut: 'planifie' }))
    const api = fauxServeur(rows)
    const res = await executerEditionStatut(api, rows, 'en_cours')
    expect(res.updated.map((u) => u.annulable)).toEqual([true, true])
  })

  it('Nouveau → En cours : retour hors graphe, « Annuler » non proposé', async () => {
    const api = fauxServeur(lignes)
    const res = await executerEditionStatut(api, lignes, 'en_cours')
    expect(res.updated).toHaveLength(2)
    expect(res.updated.every((u) => u.annulable === false)).toBe(true)
  })

  it('annulation refusée par le serveur : échecs comptés, jamais « annulée »', async () => {
    const api = fauxServeur(lignes)
    const { updated } = await executerEditionStatut(api, lignes, 'en_cours')
    const r = await annulerEditionStatut(api, updated)
    expect(r).toEqual({ nbTraites: 0, nbEchecs: 2 })
    expect([...api.etat.values()]).toEqual(['en_cours', 'en_cours'])
  })

  it('annulation permise : succès sans échec', async () => {
    const api = fauxServeur([{ id: 1, statut: 'nouveau' }])
    const { updated } = await executerEditionStatut(api, [{ id: 1, reference: 'S', statut: 'nouveau' }], 'planifie')
    expect(updated[0].annulable).toBe(true)
    expect(await annulerEditionStatut(api, updated)).toEqual({ nbTraites: 1, nbEchecs: 0 })
  })

  it('parseBulkResult lit echecs / nb_echecs du serveur', () => {
    expect(parseBulkResult({ traites: [1], echecs: [{ id: 2, raison: 'x' }] }))
      .toMatchObject({ nbTraites: 1, nbEchecs: 1 })
    expect(parseBulkResult(undefined)).toMatchObject({ nbTraites: 0, nbEchecs: 0 })
  })
})
