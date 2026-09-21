// AOF74 — Conversions écran↔monde, zoom/pan par matrice, grille adaptative,
// niveau de détail. Logique PURE (node:test — aucune dépendance, aucun React,
// aucun DOM) : c'est la moitié testable du canvas SVG en mètres.
import test from 'node:test'
import assert from 'node:assert/strict'
import {
  LARGEUR_MIN_M,
  LARGEUR_MAX_M,
  SEUIL_AGREGATION,
  agregerParRangee,
  ajusterAVue,
  bboxDePoints,
  conformerAspect,
  creerViewport,
  deplacerPixels,
  doitAgreger,
  ecranVersMonde,
  formatMetres,
  graduations,
  metresParPixel,
  mondeVersEcran,
  pasDeGrille,
  pixelsParMetre,
  reduireViewport,
  texteEchelle,
  viewBoxDe,
  zoomerAuCentre,
  zoomerAutour,
} from './useViewport.js'

const TAILLE = { largeur: 800, hauteur: 400 }
// 200 m × 100 m visibles, coin bas-gauche à l'origine → 4 px/m, aspect conforme.
const VP = creerViewport(0, 0, 200, 100)

const proche = (a, b, eps = 1e-9) => Math.abs(a - b) <= eps

/* ═══════════ Conversions écran ↔ monde ═══════════ */

test('mondeVersEcran : l’origine du monde est le coin BAS-gauche de l’écran', () => {
  const p = mondeVersEcran({ x: 0, y: 0 }, VP, TAILLE)
  assert.ok(proche(p.x, 0))
  assert.ok(proche(p.y, 400)) // bas de l'élément
})

test('mondeVersEcran : x va vers l’EST (droite) et y vers le NORD (haut de l’écran)', () => {
  const origine = mondeVersEcran({ x: 0, y: 0 }, VP, TAILLE)
  const est = mondeVersEcran({ x: 50, y: 0 }, VP, TAILLE)
  const nord = mondeVersEcran({ x: 0, y: 50 }, VP, TAILLE)
  assert.ok(est.x > origine.x, 'x monde croissant → x écran croissant')
  assert.ok(nord.y < origine.y, 'y monde croissant (nord) → y écran DÉCROISSANT')
})

test('mondeVersEcran : le coin haut-droit du monde visible est (largeur, 0)', () => {
  const p = mondeVersEcran({ x: 200, y: 100 }, VP, TAILLE)
  assert.ok(proche(p.x, 800))
  assert.ok(proche(p.y, 0))
})

test('ecranVersMonde ∘ mondeVersEcran = identité (aller-retour exact)', () => {
  const points = [
    { x: 0, y: 0 }, { x: 12.5, y: 7.25 }, { x: 199.99, y: 99.99 },
    { x: -30, y: 250 }, { x: 1234.5678, y: -987.6543 },
  ]
  for (const p of points) {
    const retour = ecranVersMonde(mondeVersEcran(p, VP, TAILLE), VP, TAILLE)
    assert.ok(proche(retour.x, p.x, 1e-9), `x: ${retour.x} ≠ ${p.x}`)
    assert.ok(proche(retour.y, p.y, 1e-9), `y: ${retour.y} ≠ ${p.y}`)
  }
})

test('mondeVersEcran ∘ ecranVersMonde = identité (aller-retour depuis l’écran)', () => {
  for (const p of [{ x: 0, y: 0 }, { x: 800, y: 400 }, { x: 317, y: 42 }]) {
    const retour = mondeVersEcran(ecranVersMonde(p, VP, TAILLE), VP, TAILLE)
    assert.ok(proche(retour.x, p.x, 1e-9))
    assert.ok(proche(retour.y, p.y, 1e-9))
  }
})

test('metresParPixel / pixelsParMetre sont inverses et cohérents avec la vue', () => {
  assert.ok(proche(metresParPixel(VP, TAILLE), 0.25))
  assert.ok(proche(pixelsParMetre(VP, TAILLE), 4))
})

test('viewBoxDe rend un viewBox à utiliser avec un groupe scale(1,-1)', () => {
  // Le haut du monde visible (y = 100) devient le MIN-Y du viewBox : -100.
  assert.equal(viewBoxDe(VP), '0 -100 200 100')
  assert.equal(viewBoxDe(creerViewport(-10, 5, 40, 20)), '-10 -25 40 20')
})

/* ═══════════ Panoramique ═══════════ */

test('deplacerPixels : glisser vers la droite fait glisser la fenêtre vers l’ouest', () => {
  const apres = deplacerPixels(VP, 80, 0, TAILLE) // 80 px = 20 m
  assert.ok(proche(apres.x, -20))
  assert.ok(proche(apres.y, 0))
  assert.ok(proche(apres.l, VP.l) && proche(apres.h, VP.h), 'le pan ne change pas le zoom')
})

test('deplacerPixels : glisser vers le bas remonte la fenêtre vers le nord', () => {
  const apres = deplacerPixels(VP, 0, 40, TAILLE) // 40 px = 10 m
  assert.ok(proche(apres.y, 10))
})

test('deplacerPixels : un point du monde suit exactement le curseur', () => {
  const pt = { x: 60, y: 30 }
  const avant = mondeVersEcran(pt, VP, TAILLE)
  const apres = mondeVersEcran(pt, deplacerPixels(VP, 37, -21, TAILLE), TAILLE)
  assert.ok(proche(apres.x - avant.x, 37, 1e-9))
  assert.ok(proche(apres.y - avant.y, -21, 1e-9))
})

/* ═══════════ Zoom ═══════════ */

test('zoomerAutour : le point de monde sous l’ancre ne bouge PAS d’un pixel', () => {
  const ancre = { x: 613, y: 92 }
  for (const facteur of [1.1, 2, 8, 0.5, 0.25]) {
    const vp2 = zoomerAutour(VP, facteur, ancre, TAILLE)
    const apres = mondeVersEcran(ecranVersMonde(ancre, VP, TAILLE), vp2, TAILLE)
    assert.ok(proche(apres.x, ancre.x, 1e-7), `facteur ${facteur} : x ${apres.x}`)
    assert.ok(proche(apres.y, ancre.y, 1e-7), `facteur ${facteur} : y ${apres.y}`)
  }
})

test('zoomerAutour : facteur > 1 rapproche (moins de mètres visibles), < 1 éloigne', () => {
  const ancre = { x: 400, y: 200 }
  assert.ok(zoomerAutour(VP, 2, ancre, TAILLE).l < VP.l)
  assert.ok(zoomerAutour(VP, 0.5, ancre, TAILLE).l > VP.l)
})

test('zoomerAutour : l’aspect est préservé (jamais de déformation)', () => {
  const vp2 = zoomerAutour(VP, 3.7, { x: 100, y: 300 }, TAILLE)
  assert.ok(proche(vp2.l / vp2.h, VP.l / VP.h, 1e-9))
})

test('zoomerAutour : bornes de zoom respectées (0,5 m … 20 km)', () => {
  let vp = VP
  for (let i = 0; i < 40; i += 1) vp = zoomerAutour(vp, 2, { x: 400, y: 200 }, TAILLE)
  assert.ok(vp.l >= LARGEUR_MIN_M - 1e-9, `plancher: ${vp.l}`)
  let large = VP
  for (let i = 0; i < 40; i += 1) large = zoomerAutour(large, 0.5, { x: 400, y: 200 }, TAILLE)
  assert.ok(large.l <= LARGEUR_MAX_M + 1e-9, `plafond: ${large.l}`)
})

test('zoomerAuCentre garde le centre de la vue fixe', () => {
  const vp2 = zoomerAuCentre(VP, 4, TAILLE)
  assert.ok(proche(vp2.x + vp2.l / 2, VP.x + VP.l / 2, 1e-9))
  assert.ok(proche(vp2.y + vp2.h / 2, VP.y + VP.h / 2, 1e-9))
})

/* ═══════════ Aspect & ajustement à la vue ═══════════ */

test('conformerAspect ÉLARGIT (jamais ne rogne) et garde le centre', () => {
  const etroit = creerViewport(0, 0, 10, 100) // très haut
  const conforme = conformerAspect(etroit, TAILLE)
  assert.ok(conforme.l >= etroit.l && conforme.h >= etroit.h, 'jamais de rognage')
  assert.ok(proche(conforme.l / conforme.h, TAILLE.largeur / TAILLE.hauteur, 1e-9))
  assert.ok(proche(conforme.x + conforme.l / 2, 5, 1e-9))
  assert.ok(proche(conforme.y + conforme.h / 2, 50, 1e-9))
})

test('bboxDePoints ignore les points invalides et rend null sur un nuage vide', () => {
  assert.equal(bboxDePoints([]), null)
  assert.equal(bboxDePoints([{ x: NaN, y: 1 }]), null)
  assert.deepEqual(
    bboxDePoints([{ x: 2, y: -3 }, { x: -1, y: 8 }, { x: 5, y: 0 }]),
    { xMin: -1, yMin: -3, xMax: 5, yMax: 8 },
  )
})

test('ajusterAVue : toute la bbox tient à l’écran, avec la marge', () => {
  const bbox = { xMin: 120, yMin: -40, xMax: 260, yMax: 30 }
  const vp = ajusterAVue(bbox, TAILLE)
  for (const p of [
    { x: bbox.xMin, y: bbox.yMin }, { x: bbox.xMax, y: bbox.yMax },
    { x: bbox.xMin, y: bbox.yMax }, { x: bbox.xMax, y: bbox.yMin },
  ]) {
    const e = mondeVersEcran(p, vp, TAILLE)
    assert.ok(e.x >= -1e-6 && e.x <= TAILLE.largeur + 1e-6, `hors cadre en x: ${e.x}`)
    assert.ok(e.y >= -1e-6 && e.y <= TAILLE.hauteur + 1e-6, `hors cadre en y: ${e.y}`)
  }
  assert.ok(proche(vp.l / vp.h, TAILLE.largeur / TAILLE.hauteur, 1e-9))
})

test('ajusterAVue : une bbox dégénérée (un seul point) ne divise pas par zéro', () => {
  const vp = ajusterAVue({ xMin: 7, yMin: 7, xMax: 7, yMax: 7 }, TAILLE)
  assert.ok(vp.l > 0 && vp.h > 0)
  assert.ok(Number.isFinite(vp.x) && Number.isFinite(vp.y))
})

test('ajusterAVue rend null sans bbox ou sans taille mesurée', () => {
  assert.equal(ajusterAVue(null, TAILLE), null)
  assert.equal(ajusterAVue({ xMin: 0, yMin: 0, xMax: 1, yMax: 1 }, { largeur: 0, hauteur: 0 }), null)
})

/* ═══════════ Grille et règles ═══════════ */

test('pasDeGrille reste sur l’échelle 1-2-5 × 10^k à tous les zooms', () => {
  const mantisses = new Set()
  for (let l = 1; l < 20000; l *= 1.37) {
    const pas = pasDeGrille(creerViewport(0, 0, l, l / 2), TAILLE)
    const exposant = Math.floor(Math.log10(pas))
    const mantisse = Number((pas / 10 ** exposant).toFixed(6))
    mantisses.add(mantisse)
  }
  for (const m of mantisses) {
    assert.ok([1, 2, 5].includes(m), `mantisse hors échelle 1-2-5 : ${m}`)
  }
})

test('pasDeGrille garde un écart à l’écran dans un facteur 2 de la cible', () => {
  for (let l = 1; l < 20000; l *= 1.37) {
    const vp = creerViewport(0, 0, l, l / 2)
    const ecartPx = pasDeGrille(vp, TAILLE, 64) * pixelsParMetre(vp, TAILLE)
    assert.ok(ecartPx >= 32 && ecartPx <= 128, `écart ${ecartPx} px pour l=${l}`)
  }
})

test('graduations : multiples du pas, dans la fenêtre, arrondis (pas de 12,000000002)', () => {
  const vp = creerViewport(3.7, -2.4, 40, 20)
  const pas = 5
  const ticks = graduations(vp, 'x', pas)
  assert.ok(ticks.length > 0)
  for (const t of ticks) {
    assert.ok(t >= vp.x - 1e-9 && t <= vp.x + vp.l + 1e-9, `hors fenêtre : ${t}`)
    assert.equal(t % pas, 0, `pas un multiple de ${pas} : ${t}`)
  }
  assert.deepEqual(ticks, [5, 10, 15, 20, 25, 30, 35, 40])
})

test('graduations sur y utilise la hauteur de la fenêtre', () => {
  const ticks = graduations(creerViewport(0, 0, 200, 100), 'y', 25)
  assert.deepEqual(ticks, [0, 25, 50, 75, 100])
})

test('graduations : pas invalide ou fenêtre nulle → aucune graduation (jamais de boucle infinie)', () => {
  assert.deepEqual(graduations(VP, 'x', 0), [])
  assert.deepEqual(graduations(VP, 'x', -1), [])
  assert.deepEqual(graduations(creerViewport(0, 0, 0, 0), 'x', 1), [])
})

test('texteEchelle bascule px/m ↔ m/px selon le zoom et formate en français', () => {
  assert.equal(texteEchelle(VP, TAILLE), '1 m = 4,0 px')
  assert.equal(texteEchelle(creerViewport(0, 0, 8000, 4000), TAILLE), '1 px = 10,0 m')
})

test('formatMetres adapte la précision au pas de grille', () => {
  assert.equal(formatMetres(12.3456, 10), '12 m')
  assert.equal(formatMetres(12.3456, 1), '12,3 m')
  assert.equal(formatMetres(12.3456, 0.5), '12,35 m')
  assert.equal(formatMetres(NaN), '—')
})

/* ═══════════ Niveau de détail (scène de 2 000 éléments) ═══════════ */

function scene2000() {
  const tables = []
  for (let rangee = 0; rangee < 40; rangee += 1) {
    for (let i = 0; i < 50; i += 1) {
      tables.push({ id: `t${rangee}-${i}`, rangee: `R${rangee}`, d: `M${i} ${rangee}h2v1h-2z` })
    }
  }
  return tables
}

test('doitAgreger : au large ET au-delà du seuil → agrégation ; au zoom → détail', () => {
  const large = creerViewport(0, 0, 400, 200) // 2 px/m
  const serre = creerViewport(0, 0, 20, 10) // 40 px/m
  assert.equal(doitAgreger(2000, large, TAILLE), true)
  assert.equal(doitAgreger(2000, serre, TAILLE), false, 'au zoom, le détail revient')
  assert.equal(doitAgreger(SEUIL_AGREGATION, large, TAILLE), false, 'petite scène : jamais agrégée')
})

test('agregerParRangee : 2 000 tables → 40 chemins (un par rangée)', () => {
  const tables = scene2000()
  assert.equal(tables.length, 2000)
  const paths = agregerParRangee(tables)
  assert.equal(paths.length, 40)
  assert.ok(paths.every((p) => typeof p.d === 'string' && p.d.length > 0))
  // Aucun segment perdu : chaque « d » d'origine se retrouve dans sa rangée.
  assert.equal(paths[0].d.split('M').length - 1, 50)
})

test('agregerParRangee ignore les tables sans tracé et regroupe les sans-rangée', () => {
  const paths = agregerParRangee([
    { id: 'a', d: 'M0 0h1' }, { id: 'b', d: '' }, { id: 'c', d: 'M2 0h1' },
  ])
  assert.equal(paths.length, 1)
  assert.equal(paths[0].rangee, 'hors-rangee')
  assert.equal(paths[0].d, 'M0 0h1 M2 0h1')
})

/* ═══════════ Réducteur ═══════════ */

test('reduireViewport : « taille » conforme l’aspect sans perdre le centre', () => {
  const etat = { viewport: creerViewport(0, 0, 100, 100), taille: { largeur: 0, hauteur: 0 } }
  const suivant = reduireViewport(etat, { type: 'taille', taille: TAILLE })
  assert.deepEqual(suivant.taille, TAILLE)
  assert.ok(proche(suivant.viewport.l / suivant.viewport.h, 2, 1e-9))
  assert.ok(proche(suivant.viewport.x + suivant.viewport.l / 2, 50, 1e-9))
})

test('reduireViewport : une taille non mesurée ne touche à rien', () => {
  const etat = { viewport: VP, taille: TAILLE }
  assert.equal(reduireViewport(etat, { type: 'taille', taille: { largeur: 0, hauteur: 0 } }), etat)
})

test('reduireViewport : deplacer / zoom / ajuster / poser', () => {
  const etat = { viewport: VP, taille: TAILLE }
  assert.ok(proche(reduireViewport(etat, { type: 'deplacer', dx: 80, dy: 0 }).viewport.x, -20))
  assert.ok(reduireViewport(etat, { type: 'zoom', facteur: 2 }).viewport.l < VP.l)
  const ajuste = reduireViewport(etat, {
    type: 'ajuster', bbox: { xMin: 0, yMin: 0, xMax: 10, yMax: 5 },
  })
  assert.ok(ajuste.viewport.l < VP.l)
  const pose = reduireViewport(etat, { type: 'poser', viewport: creerViewport(0, 0, 50, 50) })
  assert.ok(proche(pose.viewport.l / pose.viewport.h, 2, 1e-9))
})

test('reduireViewport : action inconnue → état inchangé (même référence)', () => {
  const etat = { viewport: VP, taille: TAILLE }
  assert.equal(reduireViewport(etat, { type: 'inexistante' }), etat)
})
