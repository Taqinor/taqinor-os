import { describe, it, expect, vi } from 'vitest'

/* EZ7 — la signature ne peut plus être oubliée : elle entre dans la SÉQUENCE
   « Prochaine action » (sur site + photos obligatoires faites), au lieu de
   rester l'onglet 9/10 que personne n'ouvrait. */

const { rejected } = vi.hoisted(() => ({
  rejected: () => Promise.reject(new Error('non mocké')),
}))
vi.mock('../../api/installationsApi', () => ({
  default: {
    getMaTournee: vi.fn(rejected),
    updateIntervention: vi.fn(rejected),
    getPreparation: vi.fn(rejected),
    getPhotos: vi.fn(rejected),
  },
}))

import { prochaineAction } from './MaJourneePage'

describe('EZ7 · la signature entre dans la séquence', () => {
  it('sur site, photos manquantes → on reste sur les photos', () => {
    expect(prochaineAction({ statut: 'sur_site', photos_obligatoires_manquantes: 2 }))
      .toEqual({ tab: 'photos', text: 'compléter les photos obligatoires.' })
  })

  it('sur site, photos OK, pas de signature → la signature', () => {
    const next = prochaineAction({ statut: 'sur_site', photos_obligatoires_manquantes: 0 })
    expect(next.tab).toBe('signature')
    expect(next.text).toMatch(/signer le client/)
  })

  it('sur site, photos OK, déjà signé → le retour dépôt', () => {
    const next = prochaineAction({
      statut: 'sur_site', photos_obligatoires_manquantes: 0, signe_le: '2026-08-01T16:00:00Z',
    })
    expect(next.tab).toBe('trajet')
  })

  it('compte de photos INCONNU → séquence historique (on ne suppose rien)', () => {
    expect(prochaineAction({ statut: 'sur_site' }))
      .toEqual({ tab: 'photos', text: 'compléter les photos obligatoires.' })
  })

  it('les autres statuts gardent leur suite d’origine', () => {
    expect(prochaineAction({ statut: 'a_preparer' }).tab).toBe('prep')
    expect(prochaineAction({ statut: 'prete' }).tab).toBe('trajet')
    expect(prochaineAction({ statut: 'en_route' }).tab).toBe('trajet')
    expect(prochaineAction({ statut: 'terminee' }).tab).toBe('outils')
    expect(prochaineAction({ statut: 'validee' })).toBeNull()
    expect(prochaineAction(null)).toBeNull()
  })
})
