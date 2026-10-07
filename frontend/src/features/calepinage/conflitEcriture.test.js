import { describe, it, expect } from 'vitest'
import { MOTIF_VERROU_PAR_DEFAUT, lireConflit } from './conflitEcriture'

/* Lot 2 critique #32 — le jeton périmé (`document_modifie`, 428) n'est JAMAIS
   confondu avec le verrou (motif serveur). */
describe('lireConflit', () => {
  it('document_modifie et 428 : « changé ailleurs »', () => {
    expect(lireConflit({ response: { status: 409, data: { code: 'document_modifie' } } }))
      .toEqual({ documentModifie: true })
    expect(lireConflit({ response: { status: 428, data: {} } }))
      .toEqual({ documentModifie: true })
  })

  it('verrou : le motif du serveur (roof_layout[0], sinon detail, sinon 1er champ)', () => {
    expect(lireConflit({ response: { status: 409, data: { roof_layout: ['Devis accepté : révisez-le'] } } }))
      .toEqual({ documentModifie: false, motif: 'Devis accepté : révisez-le' })
    expect(lireConflit({ response: { status: 409, data: { detail: 'Calepinage archivé' } } }))
      .toEqual({ documentModifie: false, motif: 'Calepinage archivé' })
    expect(lireConflit({ response: { status: 409, data: { systeme_id: ['Verrouillé'] } } }))
      .toEqual({ documentModifie: false, motif: 'Verrouillé' })
    expect(lireConflit({ response: { status: 409, data: {} } }))
      .toEqual({ documentModifie: false, motif: MOTIF_VERROU_PAR_DEFAUT })
  })

  it('hors conflit : null', () => {
    expect(lireConflit({ response: { status: 400, data: {} } })).toBeNull()
    expect(lireConflit(new Error('réseau'))).toBeNull()
  })
})
