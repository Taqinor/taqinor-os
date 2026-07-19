// WIR71 — lectures obligatoires KB (XKB7) surfacées sur ArticleDetail :
// wrappers kbApi + badge « Lecture obligatoire » + assignation manager.
// Vérification de SOURCE (JSX, pas de node_modules dans ce lane).
//   node --test src/features/kb/lecture-obligatoire-wir71.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const DETAIL = readFileSync(join(HERE, 'ArticleDetail.jsx'), 'utf8')
const API = readFileSync(join(HERE, '..', '..', 'api', 'kbApi.js'), 'utf8')

test('kbApi expose les wrappers lectures-obligatoires (list/create/remove)', () => {
  assert.match(API, /listLecturesObligatoires:[\s\S]*?\/kb\/lectures-obligatoires\//)
  assert.match(API, /createLectureObligatoire:/)
  assert.match(API, /removeLectureObligatoire:/)
})

test('ArticleDetail charge les lectures obligatoires de l’article', () => {
  assert.match(DETAIL, /kbApi\.listLecturesObligatoires\(\{ article: articleId \}\)/)
  assert.match(DETAIL, /setLecturesObl\(/)
})

test('un badge « Lecture obligatoire » s’affiche quand une assignation existe', () => {
  assert.match(DETAIL, /lecturesObl\.length > 0 &&/)
  assert.match(DETAIL, /Lecture obligatoire/)
})

test('un manager peut assigner/retirer via createLectureObligatoire/removeLectureObligatoire', () => {
  assert.match(DETAIL, /kbApi\.createLectureObligatoire\(\{[\s\S]*?article: articleId/)
  assert.match(DETAIL, /kbApi\.removeLectureObligatoire\(id\)/)
})
