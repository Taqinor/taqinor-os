import test from 'node:test'
import assert from 'node:assert/strict'

import {
  rotatedDims,
  normalizeRotation,
  rotationTransform,
  makeCapturedPage,
  rotatePageInList,
  removePageFromList,
} from './capture.js'

test('rotatedDims garde les dimensions à 0°/180°', () => {
  assert.deepEqual(rotatedDims(100, 60, 0), { width: 100, height: 60 })
  assert.deepEqual(rotatedDims(100, 60, 180), { width: 100, height: 60 })
})

test('rotatedDims permute largeur/hauteur à 90°/270°', () => {
  assert.deepEqual(rotatedDims(100, 60, 90), { width: 60, height: 100 })
  assert.deepEqual(rotatedDims(100, 60, 270), { width: 60, height: 100 })
  assert.deepEqual(rotatedDims(100, 60, -90), { width: 60, height: 100 })
})

test('normalizeRotation ramène tout angle à un cran de 0/90/180/270', () => {
  assert.equal(normalizeRotation(0), 0)
  assert.equal(normalizeRotation(90), 90)
  assert.equal(normalizeRotation(360), 0)
  assert.equal(normalizeRotation(450), 90)
  assert.equal(normalizeRotation(-90), 270)
  assert.equal(normalizeRotation(-180), 180)
})

test('rotationTransform renvoie une transformation identité à 0°', () => {
  assert.deepEqual(
    rotationTransform(0, 100, 60), { translateX: 0, translateY: 0, angleRad: 0 })
})

test('rotationTransform translate+pivote pour 90/180/270', () => {
  const r90 = rotationTransform(90, 100, 60)
  assert.equal(r90.translateX, 60)
  assert.equal(r90.translateY, 0)
  const r180 = rotationTransform(180, 100, 60)
  assert.equal(r180.translateX, 100)
  assert.equal(r180.translateY, 60)
  const r270 = rotationTransform(270, 100, 60)
  assert.equal(r270.translateX, 0)
  assert.equal(r270.translateY, 100)
})

test('makeCapturedPage construit une entrée avec rotation=0', () => {
  const file = { name: 'a.jpg' }
  const page = makeCapturedPage(1, file)
  assert.deepEqual(page, { id: 1, file, rotation: 0 })
})

test('rotatePageInList incrémente de 90 uniquement la page ciblée', () => {
  const pages = [makeCapturedPage(1, {}), makeCapturedPage(2, {})]
  const next = rotatePageInList(pages, 1)
  assert.equal(next[0].rotation, 90)
  assert.equal(next[1].rotation, 0)
})

test('rotatePageInList boucle 270 -> 0', () => {
  const pages = [{ id: 1, file: {}, rotation: 270 }]
  const next = rotatePageInList(pages, 1)
  assert.equal(next[0].rotation, 0)
})

test('removePageFromList retire uniquement la page ciblée', () => {
  const pages = [makeCapturedPage(1, {}), makeCapturedPage(2, {})]
  const next = removePageFromList(pages, 1)
  assert.deepEqual(next.map((p) => p.id), [2])
})
