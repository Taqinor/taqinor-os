import { describe, it, expect } from 'vitest'
import { mesChiffresDuMois, leadsChauds } from './Dashboard.jsx'

/* VX219 — « Mes chiffres » : le vendeur `normal` voit ENFIN sa propre
   performance. On teste les fonctions PURES qui dérivent les compteurs
   personnels (devis du mois, leads chauds) des slices déjà chargées — sans
   monter le composant ni le store. La carte n'agrège JAMAIS l'équipe : chaque
   test vérifie explicitement le scope `userId`. */

const NOW = new Date('2026-07-11T09:00:00')

describe('mesChiffresDuMois (VX219)', () => {
  const devis = [
    // Moi (42), ce mois, envoyé.
    { id: 1, created_by: 42, statut: 'envoye', date_creation: '2026-07-05', total_ttc: '10000' },
    // Moi (42), ce mois, accepté (compte aussi comme « émis »).
    { id: 2, created_by: 42, statut: 'accepte', date_creation: '2026-07-08', total_affiche: '25000' },
    // Moi (42), ce mois, brouillon → pas « émis ».
    { id: 3, created_by: 42, statut: 'brouillon', date_creation: '2026-07-09', total_ttc: '5000' },
    // Un autre vendeur (7) — ne doit JAMAIS être compté dans mes chiffres.
    { id: 4, created_by: 7, statut: 'accepte', date_creation: '2026-07-08', total_ttc: '99999' },
    // Moi (42), mais mois précédent → hors fenêtre.
    { id: 5, created_by: 42, statut: 'accepte', date_creation: '2026-06-20', total_ttc: '15000' },
  ]

  it('scope au vendeur courant et au mois courant', () => {
    const r = mesChiffresDuMois(devis, { userId: 42, now: NOW })
    expect(r.envoyes).toBe(2) // #1 envoyé + #2 accepté
    expect(r.acceptes).toBe(1) // #2 seul
    expect(r.tauxSignature).toBe(50) // 1/2
    expect(r.caSigne).toBe(25000) // total_affiche du #2 uniquement
  })

  it('un autre vendeur (7) reste hors de MES chiffres', () => {
    const r = mesChiffresDuMois(devis, { userId: 42, now: NOW })
    // Le devis #4 (99999, vendeur 7) ne doit apparaître nulle part.
    expect(r.caSigne).not.toBe(99999 + 25000)
  })

  it('sans devis ce mois → zéros propres, jamais une exception', () => {
    const r = mesChiffresDuMois([], { userId: 42, now: NOW })
    expect(r).toEqual({ envoyes: 0, acceptes: 0, tauxSignature: 0, caSigne: 0 })
  })

  it('userId absent → aucun filtre par vendeur (repli société, jamais un crash)', () => {
    const r = mesChiffresDuMois(devis, { now: NOW })
    expect(r.envoyes).toBe(3) // #1, #2, #4 (tous ce mois, hors brouillon/hors juin)
  })
})

describe('leadsChauds (VX219)', () => {
  const leads = [
    { id: 1, nom: 'A', owner: 42, score: 30 },
    { id: 2, nom: 'B', owner: 42, score: 90 },
    { id: 3, nom: 'C', owner: 42, score: 60 },
    { id: 4, nom: 'D', owner: 42, score: 10 },
    { id: 5, nom: 'E', owner: 7, score: 99 }, // autre vendeur → jamais dans MES leads chauds
    { id: 6, nom: 'F', owner: 42, score: 95, perdu: true }, // perdu → exclu
    { id: 7, nom: 'G', owner: 42, score: 95, is_archived: true }, // archivé → exclu
  ]

  it('trie par score décroissant, plafonne à 3, scope au vendeur', () => {
    const r = leadsChauds(leads, { userId: 42, limit: 3 }).map((l) => l.id)
    expect(r).toEqual([2, 3, 1])
  })

  it("un lead d'un autre vendeur n'apparaît jamais", () => {
    const r = leadsChauds(leads, { userId: 42, limit: 10 }).map((l) => l.id)
    expect(r).not.toContain(5)
  })

  it('score absent → traité comme 0 (jamais une exception)', () => {
    const r = leadsChauds([{ id: 9, owner: 42 }], { userId: 42 })
    expect(r).toEqual([{ id: 9, owner: 42 }])
  })
})
