import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  creerCoteDeduite,
  normaliserCote,
  ecartAnnonce,
  pointsALever,
  coherentes,
  exporterPointsALever,
  PROVENANCE_A_CONFIRMER,
  PROVENANCE_MESURE,
  ORIGINE_DEDUCTION,
} from './deduction.js'

/* AOF87 — le CAS RÉEL : la profondeur de cage n'a jamais été mesurée, elle est
   déduite de la fermeture (51,10 − 42,28 = 8,82) alors que le client annonçait
   « ≈ 8,5 » ; et la largeur relevée à 25,62 contre 26,20 au plan (Δ 0,58). */

test('la profondeur de cage se DÉDUIT de la fermeture — 51,10 − 42,28 = 8,82', () => {
  const cage = creerCoteDeduite({
    id: 'cage',
    libelle: 'Profondeur de cage',
    total: 51.1,
    connus: [42.28],
    valeurAnnoncee: 8.5,
  })
  assert.equal(cage.valeur, 8.82)
  assert.equal(cage.origine, ORIGINE_DEDUCTION)
})

test('une cote déduite ne peut PAS rester bleue : elle bascule toute seule en « à confirmer »', () => {
  const cage = creerCoteDeduite({ id: 'cage', libelle: 'Cage', total: 51.1, connus: [42.28] })
  assert.equal(cage.provenance, PROVENANCE_A_CONFIRMER)

  // Même en forçant la main : la règle vit dans normaliserCote, pas dans l'écran.
  const force = normaliserCote({ ...cage, provenance: PROVENANCE_MESURE })
  assert.equal(force.provenance, PROVENANCE_A_CONFIRMER)
  assert.deepEqual(coherentes([force]), [])
})

test('l’écart avec la valeur annoncée est écrit EN CLAIR (+0,32 m sur 8,5 annoncés)', () => {
  const cage = creerCoteDeduite({
    id: 'cage',
    libelle: 'Cage',
    total: 51.1,
    connus: [42.28],
    valeurAnnoncee: 8.5,
  })
  const e = ecartAnnonce(cage)
  assert.equal(e.ecart, 0.32)
  assert.match(e.texte, /\+0,32 m/)
  assert.match(e.texte, /8,50 m annoncés/)
})

test('la section « à lever » se remplit TOUTE SEULE — déduction + divergence', () => {
  const cotes = [
    creerCoteDeduite({
      id: 'cage',
      libelle: 'Profondeur de cage',
      total: 51.1,
      connus: [42.28],
      valeurAnnoncee: 8.5,
    }),
    // Largeur bel et bien MESURÉE, mais divergente du plan : l'écart se publie.
    {
      id: 'largeur',
      libelle: 'Largeur bâtiment',
      valeur: 25.62,
      provenance: PROVENANCE_MESURE,
      valeurAnnoncee: 26.2,
    },
    // Cote mesurée conforme : elle n'a rien à faire dans la section.
    {
      id: 'longueur',
      libelle: 'Longueur bâtiment',
      valeur: 51.1,
      provenance: PROVENANCE_MESURE,
      valeurAnnoncee: 51.1,
    },
  ]

  const points = pointsALever(cotes)
  assert.equal(points.length, 2)

  const cage = points.find((p) => p.id === 'cage')
  assert.equal(cage.motif, 'deduction')
  assert.equal(cage.provenance, PROVENANCE_A_CONFIRMER)
  assert.equal(cage.ecart, 0.32)
  assert.match(cage.formule, /51\.1/)

  const largeur = points.find((p) => p.id === 'largeur')
  assert.equal(largeur.motif, 'divergence')
  assert.equal(largeur.ecart, -0.58) // 25,62 − 26,20 : Δ 0,58 publié
  assert.match(largeur.texteEcart, /-0,58 m/)

  assert.equal(points.some((p) => p.id === 'longueur'), false)
})

test('une divergence sous le seuil (bruit de relevé) n’encombre pas la section', () => {
  const points = pointsALever([
    {
      id: 'x',
      libelle: 'Petit décalage',
      valeur: 12.72,
      provenance: PROVENANCE_MESURE,
      valeurAnnoncee: 12.7,
    },
  ])
  assert.equal(points.length, 0)
})

test('la section est EXPORTABLE (CSV français, décimale à la virgule)', () => {
  const points = pointsALever([
    creerCoteDeduite({
      id: 'cage',
      libelle: 'Profondeur de cage',
      total: 51.1,
      connus: [42.28],
      valeurAnnoncee: 8.5,
    }),
  ])
  const csv = exporterPointsALever(points)
  const lignes = csv.split('\n')
  assert.match(lignes[0], /^Repère;Cote \(m\);Provenance;Motif;Écart \(m\);Détail$/)
  assert.match(lignes[1], /^Profondeur de cage;8,82;à confirmer;cote déduite;\+?0,32;/)
})

test('une déduction sans valeur annoncée reste listée, sans écart inventé', () => {
  const points = pointsALever([
    creerCoteDeduite({ id: 'z', libelle: 'Retour', total: 30, connus: [12, 5] }),
  ])
  assert.equal(points.length, 1)
  assert.equal(points[0].valeur, 13)
  assert.equal(points[0].ecart, null)
  assert.equal(points[0].texteEcart, null)
})

test('un `total` non numérique est refusé plutôt que déduit de travers', () => {
  assert.throws(() => creerCoteDeduite({ id: 'a', total: 'douze', connus: [1] }), /total/)
})
