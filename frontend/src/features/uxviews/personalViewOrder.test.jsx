// NTUX21 — ordre des vues personnelles, persisté en localStorage (jamais
// côté serveur, contrairement aux favoris).
import { describe, it, expect, beforeEach } from 'vitest'
import { readOrder, writeOrder, applyOrder } from './personalViewOrder'

beforeEach(() => { localStorage.clear() })

describe('readOrder/writeOrder (NTUX21)', () => {
  it('renvoie [] sans rien enregistré', () => {
    expect(readOrder('crm.leads')).toEqual([])
  })

  it('persiste puis relit le même ordre', () => {
    writeOrder('crm.leads', [3, 1, 2])
    expect(readOrder('crm.leads')).toEqual([3, 1, 2])
  })

  it('une clé PAR écran — jamais partagée entre écrans', () => {
    writeOrder('crm.leads', [1, 2])
    writeOrder('ventes.devis', [9, 8])
    expect(readOrder('crm.leads')).toEqual([1, 2])
    expect(readOrder('ventes.devis')).toEqual([9, 8])
  })
})

describe('applyOrder (NTUX21)', () => {
  const list = [{ id: 1, nom: 'A' }, { id: 2, nom: 'B' }, { id: 3, nom: 'C' }]

  it('sans ordre enregistré, renvoie la liste telle quelle', () => {
    expect(applyOrder(list, [])).toEqual(list)
  })

  it('réordonne selon l’ordre mémorisé', () => {
    expect(applyOrder(list, [3, 1, 2]).map((v) => v.id)).toEqual([3, 1, 2])
  })

  it('un élément NOUVEAU (jamais vu) est ajouté à la fin, jamais perdu', () => {
    const withNew = [...list, { id: 4, nom: 'D' }]
    expect(applyOrder(withNew, [2, 1]).map((v) => v.id)).toEqual([2, 1, 3, 4])
  })

  it('un id mémorisé mais SUPPRIMÉ depuis (vue effacée) ne casse rien', () => {
    expect(applyOrder(list, [99, 1, 2]).map((v) => v.id)).toEqual([1, 2, 3])
  })
})
