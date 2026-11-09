import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import { mesChiffresDuMois, moisCourant, leadsChauds } from './Dashboard.jsx'

const ICI = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(ICI, 'Dashboard.jsx'), 'utf8')
const CONTRATS = join(ICI, '..', '..', '..', 'backend', 'django_core', 'apps')
// AANA60 — réponses CHARGÉES depuis les contrats partagés (jamais inventées).
const Q2C = JSON.parse(readFileSync(join(CONTRATS, 'ventes', 'contract_samples', 'dashboard_q2c.json'), 'utf8')).exemple
const REPORTING = JSON.parse(readFileSync(join(CONTRATS, 'reporting', 'contract_samples', 'dashboard.json'), 'utf8')).exemple

/* VX219 — « Mes chiffres » : le vendeur `normal` voit ENFIN sa propre
   performance. On teste les fonctions PURES qui dérivent les compteurs
   personnels (devis du mois, leads chauds) des slices déjà chargées — sans
   monter le composant ni le store. La carte n'agrège JAMAIS l'équipe : chaque
   test vérifie explicitement le scope `userId`. */

const NOW = new Date('2026-07-11T09:00:00')

describe('mesChiffresDuMois (VX219, AANA60 : taux servi)', () => {
  const devis = [
    // Moi (42), ce mois, envoyé.
    { id: 1, created_by: 42, statut: 'envoye', date_creation: '2026-07-05', total_ttc: '10000' },
    // Moi (42), ce mois, accepté.
    { id: 2, created_by: 42, statut: 'accepte', date_creation: '2026-07-08', total_affiche: '25000' },
    // Un autre vendeur (7) — ne doit JAMAIS être compté dans mes chiffres.
    { id: 4, created_by: 7, statut: 'accepte', date_creation: '2026-07-08', total_ttc: '99999' },
    // Moi (42), mais mois précédent → hors fenêtre.
    { id: 5, created_by: 42, statut: 'accepte', date_creation: '2026-06-20', total_ttc: '15000' },
  ]

  it('taux et effectifs = ceux SERVIS (mine=1), jamais recalculés sur la liste', () => {
    const r = mesChiffresDuMois(Q2C.devis, devis, { userId: 42, now: NOW })
    expect(r.envoyes).toBe(Q2C.devis.envoyes_periode)
    expect(r.acceptes).toBe(Q2C.devis.acceptes_periode)
    expect(r.tauxSignature).toBe(Q2C.devis.taux_acceptation_pct)
    expect(r.caSigne).toBe(25000) // total_affiche du #2 uniquement (vendeur 42, ce mois)
  })

  it('sans réponse servie → zéros propres, jamais une exception', () => {
    expect(mesChiffresDuMois(undefined, [], { userId: 42, now: NOW }))
      .toEqual({ envoyes: 0, acceptes: 0, tauxSignature: 0, caSigne: 0 })
  })

  it('moisCourant donne le paramètre month AAAA-MM', () => {
    expect(moisCourant(NOW)).toBe('2026-07')
  })
})

describe('accueil lit le taux servi (AANA60)', () => {
  it("Dashboard.jsx ne divise plus aucun effectif et lit les deux contrats servis", () => {
    // Mutant : rétablir le mémo `conversion` (signes / emis) ⇒ ce test échoue.
    expect(SRC).not.toMatch(/\.length\s*\/\s*\w+/)
    expect(SRC).not.toMatch(/signes\s*\/\s*emis/)
    expect(SRC).toContain('ventesApi.getDashboardQuoteToCash({ month: moisCourant(), mine: 1 })')
    expect(SRC).toContain('reportingApi.getDashboard()')
    expect(SRC).toContain('servis.q2c?.devis?.taux_acceptation_pct')
    expect(SRC).toContain('servis.reporting?.ca_mensuel')
    // Plus aucune somme locale des factures payées pour le CA mensuel.
    expect(SRC).not.toMatch(/statut === 'payee'/)
  })

  it('les clés lues existent dans les contrats partagés (PACT10)', () => {
    for (const k of ['taux_acceptation_pct', 'envoyes_periode', 'acceptes_periode']) {
      expect(Q2C.devis).toHaveProperty(k)
    }
    expect(Array.isArray(REPORTING.ca_mensuel)).toBe(true)
    expect(REPORTING.ca_mensuel[0]).toHaveProperty('mois')
    expect(REPORTING.ca_mensuel[0]).toHaveProperty('ca')
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
