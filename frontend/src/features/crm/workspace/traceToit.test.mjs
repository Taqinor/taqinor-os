// L-DESSIN — tests du module PUR qui transforme le contour du client en forme
// affichable. Exécutés en CI par `node --test "src/**/*.test.mjs"`.
import test from 'node:test'
import assert from 'node:assert/strict'

import {
  COTE_DESSIN,
  centreContour,
  dessinerContour,
  formaterSurface,
  lienCarte,
  normaliserContour,
  normaliserEpingle,
} from './traceToit.js'

// Un carré d'environ 20 m de côté à Casablanca, dans l'ordre d'axes RÉEL de
// `Lead.roof_outline` : [lat, lng]. 20 m ≈ 0.00018° de latitude.
const LAT0 = 33.589
const LNG0 = -7.603
const D_LAT = 0.00018
const D_LNG = 0.000216 // ≈ 20 m à cette latitude (cos(33.589°) ≈ 0.833)
const CARRE = [
  [LAT0, LNG0],
  [LAT0, LNG0 + D_LNG],
  [LAT0 + D_LAT, LNG0 + D_LNG],
  [LAT0 + D_LAT, LNG0],
]

test('normaliserContour accepte les deux formes et exige 3 sommets', () => {
  assert.equal(normaliserContour(CARRE).length, 4)
  assert.deepEqual(
    normaliserContour([{ lat: 33, lng: -7 }, { lat: 33.001, lng: -7 }, { lat: 33.001, lng: -7.001 }]),
    [[33, -7], [33.001, -7], [33.001, -7.001]],
  )
  // Moins de 3 sommets valides = pas un polygone (même règle que le webhook).
  assert.deepEqual(normaliserContour([[33, -7], [33.001, -7]]), [])
  assert.deepEqual(normaliserContour('pas-une-liste'), [])
  assert.deepEqual(normaliserContour(null), [])
  // Sommets hors bornes écartés → il en reste 2 → refus.
  assert.deepEqual(normaliserContour([[33, -7], [999, -7], [33.001, -7.001]]), [])
})

test('normaliserEpingle borne lat/lng et refuse le reste', () => {
  assert.deepEqual(normaliserEpingle({ lat: 33.5, lng: -7.6 }), { lat: 33.5, lng: -7.6 })
  assert.equal(normaliserEpingle({ lat: 91, lng: -7.6 }), null)
  assert.equal(normaliserEpingle({ lat: 33.5 }), null)
  assert.equal(normaliserEpingle(null), null)
})

test('dessinerContour rend un polygone SVG à la bonne échelle, nord en haut', () => {
  const d = dessinerContour(CARRE)
  assert.ok(d, 'un carré de 4 sommets doit produire un dessin')
  assert.equal(d.sommets, 4)
  // Carré ⇒ largeur ≈ hauteur ≈ le côté normalisé.
  assert.ok(Math.abs(d.largeur - COTE_DESSIN) < 1, `largeur=${d.largeur}`)
  assert.ok(Math.abs(d.hauteur - COTE_DESSIN) < 1, `hauteur=${d.hauteur}`)
  // 4 paires "x,y" séparées par des espaces.
  const paires = d.points.split(' ')
  assert.equal(paires.length, 4)
  for (const p of paires) assert.match(p, /^-?\d+(\.\d)?,-?\d+(\.\d)?$/)
  // NORD EN HAUT : le sommet de latitude MAXIMALE doit avoir le y SVG le plus
  // petit (l'axe y du SVG descend). Sommets 2 et 3 sont les plus au nord.
  const ys = paires.map((p) => Number(p.split(',')[1]))
  assert.ok(Math.max(ys[2], ys[3]) < Math.min(ys[0], ys[1]),
    `les sommets nord doivent être en haut : ${d.points}`)
})

test('dessinerContour mesure une surface RÉELLE (jamais un défaut)', () => {
  const d = dessinerContour(CARRE)
  // ~20 m × ~20 m ≈ 400 m². Tolérance large : on épingle l'ordre de grandeur
  // (donc l'ordre des axes), pas la 3e décimale du modèle géodésique.
  assert.ok(d.aireM2 > 300 && d.aireM2 < 520, `aire=${d.aireM2}`)
  assert.ok(d.largeurM > 15 && d.largeurM < 25, `largeurM=${d.largeurM}`)
  assert.ok(d.hauteurM > 15 && d.hauteurM < 25, `hauteurM=${d.hauteurM}`)
})

test('dessinerContour refuse ce qui n\'est pas affichable', () => {
  assert.equal(dessinerContour(null), null)
  assert.equal(dessinerContour([[33, -7], [33.001, -7]]), null)
  // Trois clics au même endroit : emprise nulle, rien à dessiner.
  assert.equal(dessinerContour([[33, -7], [33, -7], [33, -7]]), null)
})

test('centreContour rend la moyenne des sommets', () => {
  const c = centreContour(normaliserContour(CARRE))
  assert.ok(Math.abs(c.lat - (LAT0 + D_LAT / 2)) < 1e-9)
  assert.ok(Math.abs(c.lng - (LNG0 + D_LNG / 2)) < 1e-9)
  assert.equal(centreContour([]), null)
})

test('formaterSurface n\'affiche jamais une surface nulle', () => {
  assert.equal(formaterSurface(0), null)
  assert.equal(formaterSurface(-3), null)
  assert.equal(formaterSurface(Number.NaN), null)
  assert.equal(formaterSurface(4.25), '4.3 m²')
  assert.equal(formaterSurface(412.7), '413 m²')
})

test('lienCarte reprend la forme du lien GPS déjà servi par la fiche', () => {
  assert.equal(lienCarte({ lat: 33.5, lng: -7.6 }), 'https://www.google.com/maps?q=33.5,-7.6')
  assert.equal(lienCarte(null), null)
})
