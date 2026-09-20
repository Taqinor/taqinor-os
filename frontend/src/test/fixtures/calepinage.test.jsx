import { describe, it, expect } from 'vitest'
import {
  ECHANTILLONS_CALEPINAGE, exempleCalepinage, reponseCalepinage,
} from './calepinage'

describe('CAL223 — fixtures de contrat du module Calepinage', () => {
  it('chaque échantillon nommé existe et porte un exemple objet', () => {
    for (const nom of ECHANTILLONS_CALEPINAGE) {
      const ex = exempleCalepinage(nom)
      expect(ex, nom).toBeTypeOf('object')
      expect(ex, nom).not.toBeNull()
    }
  })

  it('la réponse mockée enveloppe l’exemple dans `data`', () => {
    const rep = reponseCalepinage('calepinage_detail')
    expect(rep.data).toEqual(exempleCalepinage('calepinage_detail'))
  })

  it('l’état vide existe pour le détail (discipline du null, jamais 0)', () => {
    const vide = exempleCalepinage('calepinage_detail', 'exemple_vide')
    expect(vide).toBeTypeOf('object')
  })
})
