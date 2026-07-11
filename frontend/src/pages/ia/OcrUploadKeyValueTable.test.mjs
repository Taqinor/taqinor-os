// VX152 — Fin des moteurs de table parallèles : OcrUpload dupliquait DEUX
// <table> Tailwind clé/valeur (champs extraits éditables dans « Analyser » +
// lecture seule dans « Documents »). Les deux convergent sur le primitif
// partagé `KeyValueTable`, alimenté par un point de rendu UNIQUE de FIELD_LABELS
// (`ocrFieldRows`). Le data-testid `ocr-field-<clé>` et l'édition sont préservés,
// donc OcrUpload.test.jsx reste vert. Vérification de SOURCE (pas de node_modules
// installés dans ce lane — cf. RolesManagementDataTable.test.mjs) :
//   node --test src/pages/ia/OcrUploadKeyValueTable.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'OcrUpload.jsx'), 'utf8')

test('OcrUpload consolide ses tables clé/valeur sur le primitif KeyValueTable partagé', () => {
  assert.match(SRC, /KeyValueTable/)
  assert.match(SRC, /<KeyValueTable/)
})

test('un SEUL point de rendu de FIELD_LABELS (fin des deux tables clé/valeur parallèles)', () => {
  // FIELD_LABELS n'est ITÉRÉ qu'une seule fois, dans l'unique helper ocrFieldRows.
  assert.equal((SRC.match(/Object\.entries\(FIELD_LABELS\)/g) || []).length, 1)
  // Plus aucune autre itération ni indexation dispersée de FIELD_LABELS.
  assert.doesNotMatch(SRC, /Object\.keys\(FIELD_LABELS\)/)
  assert.doesNotMatch(SRC, /FIELD_LABELS\[/)
})

test("l'édition vérifier-puis-corriger reste branchée (data-testid + aria-label conservés)", () => {
  assert.match(SRC, /data-testid=\{`ocr-field-\$\{it\.key\}`\}/)
  assert.match(SRC, /aria-label=\{it\.label\}/)
})
