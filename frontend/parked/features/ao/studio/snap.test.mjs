// AOF76 — Accrochage, transformations et GARDE DE VALIDITÉ (node:test, pur).
// La règle du contrat prouvée ici : aucune manipulation ne peut produire une
// géométrie invalide — l'auto-intersection est REFUSÉE, exactement comme la
// garde W76 du traceur public.
import test from 'node:test'
import assert from 'node:assert/strict'
import {
  MIN_SOMMETS,
  PAS_ANGLE_DEG,
  accrocher,
  accrocherAlignement,
  accrocherAngle,
  accrocherSommet,
  aire,
  appliquerSiValide,
  azimutAretePrincipale,
  basculerSelection,
  centreDe,
  dansRectangle,
  deplacerPoints,
  distance,
  indicesDansRectangle,
  perimetre,
  pivoterPoints,
  polygoneSimple,
  rectangleDe,
  redimensionnerPoints,
  segmentsSeCroisent,
  toleranceMetres,
  verifierGeometrie,
} from './snap.js'

const CARRE = [{ x: 0, y: 0 }, { x: 10, y: 0 }, { x: 10, y: 10 }, { x: 0, y: 10 }]
// Pentagone simple : déplacer son sommet D sous la base fait CROISER l'arête
// C→D avec l'arête A→B — le nœud papillon canonique d'un relevé raté.
const PENTAGONE = [
  { x: 0, y: 0 }, { x: 10, y: 0 }, { x: 10, y: 10 }, { x: 5, y: 15 }, { x: 0, y: 10 },
]
const proche = (a, b, eps = 1e-9) => Math.abs(a - b) <= eps

/* ═══════════ Garde d'auto-intersection (le cœur du contrat) ═══════════ */

test('segmentsSeCroisent : croisement franc oui, parallèles et colinéaires non', () => {
  assert.equal(
    segmentsSeCroisent({ x: 0, y: 0 }, { x: 10, y: 10 }, { x: 0, y: 10 }, { x: 10, y: 0 }),
    true,
  )
  // Parallèles disjoints.
  assert.equal(
    segmentsSeCroisent({ x: 0, y: 0 }, { x: 10, y: 0 }, { x: 0, y: 5 }, { x: 10, y: 5 }),
    false,
  )
  // Colinéaires (même droite) : tous les produits vectoriels sont nuls.
  assert.equal(
    segmentsSeCroisent({ x: 0, y: 0 }, { x: 10, y: 0 }, { x: 5, y: 0 }, { x: 15, y: 0 }),
    false,
  )
  // Deux arêtes ADJACENTES partagent une extrémité : le test d'orientation les
  // compte comme croisantes — sans conséquence, `polygoneSimple` ne compare
  // JAMAIS deux arêtes adjacentes (même choix que le garde W76 public).
  assert.equal(
    segmentsSeCroisent({ x: 0, y: 0 }, { x: 10, y: 0 }, { x: 10, y: 0 }, { x: 10, y: 10 }),
    true,
  )
})

test('polygoneSimple : un carré est simple, un nœud papillon ne l’est pas', () => {
  assert.equal(polygoneSimple(CARRE), true)
  // Sommets 2 et 3 échangés → sablier.
  const papillon = [{ x: 0, y: 0 }, { x: 10, y: 0 }, { x: 0, y: 10 }, { x: 10, y: 10 }]
  assert.equal(polygoneSimple(papillon), false)
})

test('polygoneSimple : moins de 4 sommets → rien à croiser', () => {
  assert.equal(polygoneSimple([]), true)
  assert.equal(polygoneSimple([{ x: 0, y: 0 }, { x: 1, y: 0 }, { x: 0, y: 1 }]), true)
})

test('polygoneSimple : un L reste simple (concave n’est pas invalide)', () => {
  const enL = [
    { x: 0, y: 0 }, { x: 10, y: 0 }, { x: 10, y: 4 },
    { x: 4, y: 4 }, { x: 4, y: 10 }, { x: 0, y: 10 },
  ]
  assert.equal(polygoneSimple(enL), true)
  assert.equal(verifierGeometrie(enL).valide, true)
})

test('verifierGeometrie refuse : trop peu de sommets, aire nulle, auto-intersection', () => {
  assert.equal(verifierGeometrie([{ x: 0, y: 0 }, { x: 1, y: 1 }]).raison, 'trop_peu_de_sommets')
  assert.equal(MIN_SOMMETS, 3)
  const aplati = [{ x: 0, y: 0 }, { x: 5, y: 0 }, { x: 10, y: 0 }]
  assert.equal(verifierGeometrie(aplati).raison, 'aire_nulle')
  const papillon = [{ x: 0, y: 0 }, { x: 10, y: 0 }, { x: 0, y: 10 }, { x: 10, y: 10 }]
  assert.equal(verifierGeometrie(papillon).raison, 'auto_intersection')
  assert.equal(verifierGeometrie([{ x: 0, y: 0 }, { x: 1, y: NaN }, { x: 2, y: 2 }]).valide, false)
})

test('appliquerSiValide : UNE porte — un déplacement croisant est REFUSÉ, l’ancienne géométrie survit', () => {
  // Tirer le sommet D (5,15) SOUS la base : l'arête C→D traverse A→B.
  assert.equal(verifierGeometrie(PENTAGONE).valide, true, 'le point de départ doit être valide')
  const casse = deplacerPoints(PENTAGONE, [3], { dx: 0, dy: -20 })
  const r = appliquerSiValide(PENTAGONE, casse)
  assert.equal(r.valide, false)
  assert.equal(r.raison, 'auto_intersection')
  assert.deepEqual(r.points, PENTAGONE, 'la géométrie précédente doit être conservée telle quelle')
  assert.ok(typeof r.message === 'string' && r.message.length > 0, 'un motif lisible est remonté')
})

test('appliquerSiValide : un déplacement licite passe', () => {
  const bouge = deplacerPoints(CARRE, [2], { dx: 3, dy: 1 })
  const r = appliquerSiValide(CARRE, bouge)
  assert.equal(r.valide, true)
  assert.equal(r.raison, null)
  assert.deepEqual(r.points, bouge)
})

/* ═══════════ Mesures ═══════════ */

test('aire / perimetre / azimut d’un carré de 10 m', () => {
  assert.ok(proche(aire(CARRE), 100))
  assert.ok(proche(perimetre(CARRE), 40))
  assert.equal(distance({ x: 0, y: 0 }, { x: 3, y: 4 }), 5)
  // Arête la plus longue : toutes égales → la première (0,0)→(10,0), plein EST.
  assert.ok(proche(azimutAretePrincipale(CARRE), 90))
})

test('azimutAretePrincipale : arête vers le nord = 0°, vers l’ouest = 270°', () => {
  const versNord = [{ x: 0, y: 0 }, { x: 0, y: 30 }, { x: 2, y: 30 }, { x: 2, y: 0 }]
  assert.ok(proche(azimutAretePrincipale(versNord), 0))
  const versOuest = [{ x: 30, y: 0 }, { x: 0, y: 0 }, { x: 0, y: 2 }, { x: 30, y: 2 }]
  assert.ok(proche(azimutAretePrincipale(versOuest), 270))
  assert.equal(azimutAretePrincipale([{ x: 1, y: 1 }]), null)
})

/* ═══════════ Transformations ═══════════ */

test('deplacerPoints ne bouge QUE les indices demandés (et ne mute pas l’entrée)', () => {
  const apres = deplacerPoints(CARRE, [0, 2], { dx: 1, dy: -2 })
  assert.deepEqual(apres[0], { x: 1, y: -2 })
  assert.deepEqual(apres[1], { x: 10, y: 0 })
  assert.deepEqual(apres[2], { x: 11, y: 8 })
  assert.deepEqual(CARRE[0], { x: 0, y: 0 }, 'entrée mutée !')
})

test('redimensionnerPoints envoie exactement une boîte sur l’autre', () => {
  const avant = { xMin: 0, yMin: 0, xMax: 10, yMax: 10 }
  const apres = { xMin: 0, yMin: 0, xMax: 20, yMax: 5 }
  const r = redimensionnerPoints(CARRE, avant, apres)
  assert.deepEqual(r[1], { x: 20, y: 0 })
  assert.deepEqual(r[2], { x: 20, y: 5 })
  assert.deepEqual(r[3], { x: 0, y: 5 })
})

test('redimensionnerPoints : boîte dégénérée → aucune transformation (jamais NaN)', () => {
  const plate = { xMin: 3, yMin: 3, xMax: 3, yMax: 3 }
  assert.deepEqual(redimensionnerPoints(CARRE, plate, plate), CARRE)
})

test('pivoterPoints de 90° autour du centre conserve l’aire et le périmètre', () => {
  const centre = centreDe(CARRE)
  assert.deepEqual(centre, { x: 5, y: 5 })
  const r = pivoterPoints(CARRE, centre, Math.PI / 2)
  assert.ok(proche(aire(r), aire(CARRE), 1e-9))
  assert.ok(proche(perimetre(r), perimetre(CARRE), 1e-9))
  assert.equal(verifierGeometrie(r).valide, true)
})

/* ═══════════ Accrochage ═══════════ */

test('accrocherSommet prend le sommet le plus proche DANS la tolérance', () => {
  const r = accrocherSommet({ x: 10.1, y: 0.05 }, CARRE, 0.25)
  assert.deepEqual(r.point, { x: 10, y: 0 })
  assert.equal(r.guides[0].type, 'sommet')
  assert.equal(accrocherSommet({ x: 5, y: 5 }, CARRE, 0.25), null, 'hors tolérance : pas d’accroche')
})

test('accrocherAngle force l’angle droit depuis l’ancre', () => {
  const ancre = { x: 0, y: 0 }
  // Presque plein est (2° de travers) à 10 m → 0,35 m d'écart perpendiculaire.
  const r = accrocherAngle({ x: 10, y: 0.2 }, ancre, 0.5, 90)
  assert.ok(r, 'l’accroche aurait dû mordre')
  assert.ok(proche(r.point.y, 0, 1e-9))
  assert.ok(proche(r.point.x, Math.hypot(10, 0.2), 1e-9), 'le rayon est conservé')
  assert.equal(r.guides[0].degres, 0)
})

test('accrocherAngle : la tolérance est PERPENDICULAIRE, pas angulaire (jamais d’accroche de force au loin)', () => {
  const ancre = { x: 0, y: 0 }
  // Même écart angulaire, mais à 200 m : 7 m de travers → refus.
  assert.equal(accrocherAngle({ x: 200, y: 7 }, ancre, 0.5, 90), null)
  assert.equal(accrocherAngle({ x: 0, y: 0 }, ancre, 0.5, 90), null, 'rayon nul')
  assert.equal(accrocherAngle({ x: 1, y: 1 }, null, 0.5), null, 'aucune ancre')
})

test('accrocherAngle : le pas par défaut couvre les 45°', () => {
  assert.equal(PAS_ANGLE_DEG, 45)
  const r = accrocherAngle({ x: 10, y: 9.9 }, { x: 0, y: 0 }, 0.5)
  assert.ok(r)
  assert.equal(r.guides[0].degres, 45)
})

test('accrocherAlignement aligne x et y INDÉPENDAMMENT', () => {
  const refs = [{ x: 10, y: 0 }, { x: 0, y: 10 }]
  const r = accrocherAlignement({ x: 10.1, y: 9.95 }, refs, 0.25)
  assert.ok(proche(r.point.x, 10))
  assert.ok(proche(r.point.y, 10))
  assert.equal(r.guides.length, 2)
  const seulX = accrocherAlignement({ x: 10.1, y: 4 }, refs, 0.25)
  assert.ok(proche(seulX.point.x, 10))
  assert.equal(seulX.point.y, 4, 'y non aligné doit rester tel quel')
  assert.equal(accrocherAlignement({ x: 4, y: 4 }, refs, 0.25), null)
})

test('accrocher : priorité SOMMET > ANGLE > ALIGNEMENT', () => {
  const ancre = { x: 0, y: 0 }
  const sommetGagne = accrocher({ x: 10.05, y: 0.05 }, {
    sommets: CARRE, references: CARRE, ancre, tolerance: 0.3,
  })
  assert.equal(sommetGagne.accroche, 'sommet')
  assert.deepEqual(sommetGagne.point, { x: 10, y: 0 })

  const angleGagne = accrocher({ x: 6, y: 0.1 }, {
    sommets: [], references: [{ x: 6.05, y: 99 }], ancre, tolerance: 0.3,
  })
  assert.equal(angleGagne.accroche, 'angle')
})

test('accrocher : rien à portée → le point brut, jamais null', () => {
  const r = accrocher({ x: 4, y: 4 }, { sommets: CARRE, references: CARRE, tolerance: 0.1 })
  assert.equal(r.accroche, null)
  assert.deepEqual(r.point, { x: 4, y: 4 })
  assert.deepEqual(r.guides, [])
})

test('accrocher : désactivé → passe-plat intégral', () => {
  const r = accrocher({ x: 10.01, y: 0 }, { actif: false, sommets: CARRE, tolerance: 5 })
  assert.deepEqual(r.point, { x: 10.01, y: 0 })
  assert.equal(r.accroche, null)
})

test('toleranceMetres convertit une tolérance ÉCRAN en mètres (constante à tout zoom)', () => {
  assert.ok(proche(toleranceMetres(0.25, 10), 2.5)) // vue large : 10 px = 2,5 m
  assert.ok(proche(toleranceMetres(0.01, 10), 0.1)) // vue serrée : 10 px = 10 cm
  assert.ok(toleranceMetres(0, 10) > 0, 'jamais une tolérance nulle')
})

/* ═══════════ Sélection ═══════════ */

test('rectangleDe normalise quel que soit le sens du glissement', () => {
  assert.deepEqual(
    rectangleDe({ x: 10, y: 10 }, { x: 2, y: 4 }),
    { xMin: 2, yMin: 4, xMax: 10, yMax: 10 },
  )
})

test('indicesDansRectangle rend les sommets réellement contenus', () => {
  const rect = rectangleDe({ x: -1, y: -1 }, { x: 5, y: 5 })
  assert.deepEqual(indicesDansRectangle(CARRE, rect), [0])
  assert.equal(dansRectangle({ x: 0, y: 0 }, rect), true)
  assert.equal(dansRectangle({ x: 10, y: 10 }, rect), false)
})

test('basculerSelection : clic simple remplace, Maj+clic bascule', () => {
  assert.deepEqual(basculerSelection([0, 1], 2, false), [2])
  assert.deepEqual(basculerSelection([0, 2], 1, true), [0, 1, 2])
  assert.deepEqual(basculerSelection([0, 1, 2], 1, true), [0, 2])
  assert.deepEqual(basculerSelection([], 3, true), [3])
})
